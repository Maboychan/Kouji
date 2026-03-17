from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from tempfile import NamedTemporaryFile
import appex, clipboard, dialogs, io, os, ui

LOCAL_DOCS: Path = Path.home() / "Documents"
TEMP_DATA_DIR: Path = LOCAL_DOCS / "temp_data"
LOG_PATH: Path = TEMP_DATA_DIR / "log.txt"
if not TEMP_DATA_DIR.is_dir(): TEMP_DATA_DIR.mkdir(parents=True, exist_ok=True)
LATEST_FILE = sorted([x for x in os.listdir(TEMP_DATA_DIR) if '.temp' in x])
if LATEST_FILE:
    LATEST_FILE: Path = LATEST_FILE[-1]
    FILE_PATH: Path = TEMP_DATA_DIR / LATEST_FILE

with open(LOG_PATH, 'w', encoding='utf-8') as f:
    f.write(f'FILE_PATH {FILE_PATH}\n')

def log(text='',end='\n'):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(str(text)+end)
#-------------------------------------------------------------------------------------------

def is_temp_data(text):
    # 温度データならTrue、それ以外ならFalseを返す。
    if not isinstance(text, str): return False
    try:
        text_list = text.split()
        if len(text_list)<3: return False
        try: datetime.strptime(text_list[0], "%Y-%m-%d")
        except ValueError: return False
        try: datetime.strptime(text_list[1], "%H:%M")
        except ValueError: return False
        if text_list[2].strip() == "": return False
        try:
            if 20 < float(text_list[2]) < 50: return True
        except ValueError: return False
        return False
    except Exception as e:
        log("error {e}")
        return e
#-------------------------------------------------------------------------------------------

def get_temp_data(text):
    # テキストから温度データを取り出しリストで返す。
    global FILE_PATH, LINES
    TEMP_DATA = text.splitlines()
    LINES = []
    for i, LINE in enumerate(TEMP_DATA):
        log(f"{i+1} {LINE}",end='')
        
        if not is_temp_data(LINE):
            log("⚠️データが認識できません。")
            continue
        DATE = LINE.split()[0]
        TIME = LINE.split()[1]
        TEMP = LINE.split()[2]
        COMMENT = " ".join(LINE.split()[3:])
        if "0️⃣" in COMMENT:
            FILE_NAME = f'{DATE.replace("-","")}.temp'
            FILE_PATH = TEMP_DATA_DIR / FILE_NAME
        log()
        LINES.append(LINE)
    return LINES
#-------------------------------------------------------------------------------------------

def append_data(LINES):
    # FILE_PATHとLINESを合体してソートして保存する。
    from pathlib import Path
    global FILE_PATH
    data = []
    if Path(FILE_PATH).is_file():
        with open(FILE_PATH, encoding='utf-8') as f:
            data = f.read().splitlines()
    data_set = set(data + LINES)
    sorted_data = sorted(data_set)
    data = [sorted_data[0]]
    # コメント違いの重複を削除
    for d in sorted_data[1:]:
        if str(data[-1]).split()[:3] == d.split()[:3]:
            log(f'⚠️ {data[-1]} == {d}')
            data[-1] = d
        else:
            data.append(d)
    with open(FILE_PATH, 'w', encoding='utf8') as f:
        f.write('\n'.join(data))
#-------------------------------------------------------------------------------------------

def roundup(n=None):
    if not n: return int(n)
    return int(n) + (int(n) < n)
#-------------------------------------------------------------------------------------------

def show_preview(ui_img):
    # 1. 土台となるビューを作成
    v = ui.View()
    v.background_color = 'black' # 画像が映えるように背景は黒
    v.name = 'Graph Preview'
    
    # 2. 画像を表示するためのImageViewを作成
    iv = ui.ImageView()
    iv.image = ui_img
    iv.content_mode = ui.CONTENT_SCALE_ASPECT_FIT # 縦横比を維持して収める
    
    # ビュー全体にImageViewを広げる
    iv.frame = v.bounds
    iv.flex = 'WH' # 画面サイズが変わっても追従するように
    
    v.add_subview(iv)
    v.width, v.height = ui_img.size
    
    # 3. 画面に表示 (popoverだとiPadで小さく表示、sheetだと下から出てきます)
    v.present('sheet', hide_title_bar=True)
    
    # 4. 2.0秒後に閉じる
    ui.delay(v.close, 2.0)
#-------------------------------------------------------------------------------------------

def make_graph(file_path=""):
    if not file_path:
        if 'FILE_PATH' in globals():
            file_path=FILE_PATH
        else:
            log("⚠️ 温度データがありません。")
            return
        
    # 温度データから折れ線グラフを返す。
    line_color = (255, 0, 0, 255)
    factor = (0.4, 0.7, 1)
    line_colors = [tuple([int(c * f) for c in line_color]) for f in factor]
    with open(file_path, encoding='utf-8') as f:
        lines = f.read().splitlines()
        lines.sort()
    DT_TEXTS = [" ".join(x.split()[:2]) for x in lines]
    DT_LIST = [datetime.strptime(x, '%Y-%m-%d %H:%M') for x in DT_TEXTS]
    TS_LIST = [datetime.timestamp(x) for x in DT_LIST]
    # 経過時間（秒）のリスト
    MIN = min(TS_LIST)
    SEC_LIST = [x - MIN for x in TS_LIST]
    # 日数
    days = SEC_LIST[-1]/(24*3600)
    DAYS = max(int(days) + (days - int(days) > 0), 2)
    # グラフサイズ
    W, H = 324 * DAYS, 480
    seconds_w = W / DAYS / (24 * 60 * 60) # 1秒
    hours_12 = W / DAYS / (24 / 12) # 12時間
    # 温度データのリスト
    temp_list = [float(x.split()[2]) for x in lines]
    TEMP_LIST = [max(min(x-25, 25), 0) for x in temp_list]
    celsius_1 = H / 25 # 1℃の高さ
    trigger_temp = celsius_1 * (38 - 25) # トリガー温度（38℃）の高さ
    
    X_LIST = [roundup(x * seconds_w) for x in SEC_LIST]
    Y_LIST = [roundup(H - y * celsius_1) for y in TEMP_LIST]
    XY_LIST = [(X_LIST[i],Y_LIST[i]) for i in range(len(X_LIST))]
    
    im = base_graph(W, H) # 背景
    gr = Image.new('RGBA', (W, H), (0, 0, 0, 0)) # グラフ
    dr = ImageDraw.Draw(gr)
    
    # 折れ線グラフの描画
    dr.line(XY_LIST, line_colors[0], 5)
    dr.line(XY_LIST, line_colors[1], 3)
    dr.line(XY_LIST, line_colors[2], 1)
    
    # トリガーラインと出麹ラインの描画
    trigger = [[gr.getpixel((x,trigger_temp)),x] for x in range(W)]
    trigger = [x for x in trigger if line_colors[2] in x]
    
    if trigger:
        trigger = trigger[0]
        dr.line((trigger[1], 0, trigger[1], H), 'red')
        dr.line((trigger[1] + hours_12, 0, trigger[1] + hours_12, H), 'red')
    
    # 背景にグラフをペースト
    im.paste(gr, (0, 0), gr)
    return im
#-------------------------------------------------------------------------------------------

def  background_image():
    W, H = 648, 480
    day_width = W // 2
    hour_width = day_width // 24
    temp_30 = int(H - (H / 25) * 5)
    temp_40 = int(H - (H / 25) * 15)
    colors = [(80, 192, 168, 255), (255, 192, 0, 255)]
    gold_line_width = 120
    blur_radius = 40
    effect_ratio = 0.3
    # gold line
    line_img = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(line_img)
    XY = [(0, temp_30), (day_width - hour_width,temp_30), (day_width + hour_width, temp_40), (W,temp_40)]
    dr.line(XY, 255, gold_line_width, joint="curve")
    # blur
    blur_img = line_img.filter(ImageFilter.GaussianBlur(blur_radius))
    blur_img = blur_img.point(lambda x: int(x * effect_ratio))
    blur_img = blur_img.convert('RGBA')
    # gradation
    gradation_line_img = Image.new('RGB', (5, 1), (0, 0, 0))
    rgb = []
    for x in range(gradation_line_img.size[0]):
        ratio = x / (gradation_line_img.size[0] - 1)
        for i in range(3):
            rgb.append(int((colors[0][i] * (1 - ratio) + colors[1][i] * ratio)))
        gradation_line_img.putpixel((x,0),tuple(rgb))
        rgb =[]
    gradation_img = gradation_line_img.resize((W,H))
    gradation_img = gradation_img.convert('RGBA')
    # blend
    img = ImageChops.add(gradation_img, blur_img)
    return img
#-------------------------------------------------------------------------------------------

def base_graph(W=648, H=480, bg_file_name='background.png'):
    # 折れ線グラフのバックグラウンド画像を返す。
    DAYS = W // 324
    grid_color = (0, 0, 255, 255)
    grid_sub_color = (0, 0, 255, 64)
    text_color = 'blue'
    
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, W-1, H-1), (0, 0, 0, 0), grid_color)
    # 水平グリッドラインを描画する。
    for i in range(5):
        y = int(i * (H / 5))
        dr.line((0, y, W, y),grid_color)
        dr.text((5, y),str(50 - i * 5),text_color)
    dr.text((5, H - 10),str(25),text_color)
    # 垂直グリッドラインを描く
    hour = 2
    for i in range(int(DAYS / (hour / 24))):
        x = int(i * (W / DAYS / 24) * hour)
        dr.line((x, 0, x, H), grid_sub_color if x != 0 else grid_color)
    hour = 12
    for i in range(int(DAYS / (hour / 24))):
        x = int((i + 1) * (W / DAYS / 24) * hour)
        dr.line((x, 0, x, H), grid_color)
        dr.text((x if x < W else x - 12, H - 10), str((i + 1) * 12), text_color)
    # グラフサイズに合わせて背景画像を引き伸ばしグリッドラインを重ねる。
    if Path(bg_file_name).is_file():
        bg = Image.open(bg_file_name).resize((W // DAYS * 2,H))
    else:
        # 背景画像がなければ作る
        bg = background_image()
    w, h = bg.size
    cr = bg.crop((w - 1, 0, w, h))
    cr = cr.resize(im.size)
    cr.paste(bg, (0, 0))
    cr.paste(im, (0, 0), im)
    return cr
#-------------------------------------------------------------------------------------------

def main():
    global FILE_PATH, LINES
    APPEX = False
    clip = clipboard.get()
    if appex.is_running_extension():
        APPEX = True
        text = appex.get_text()
        images = appex.get_images()
        if text:
            LINES = get_temp_data(text)
            log(f'📤 {"/".join(FILE_PATH.parts[-4:])}に追加しました。')
            append_data(LINES)
        elif images:
            for i, img in enumerate(images):
                save_name = FILE_PATH.with_stem(FILE_PATH.stem + f"_haze_{i}").with_suffix(".png")
                img.save(save_name)
                log(f'🖼 {"/".join(save_name.parts[-4:])}に保存しました。')
                
    elif clip:
        LINES = get_temp_data(clip)
        if LINES:
            title = '📋 Clipboard'
            message = "クリップボードに温度データがあります。\nファイルに追加しますか?"
            y, n = 'はい', 'いいえ'
            if dialogs.alert(title, message, y, n, hide_cancel_button=True) == 1:
                log(f'📋 {"/".join(FILE_PATH.parts[-4:])}に追加しました。')
                append_data(LINES)
                
    # グラフ描画、保存、クリップボードにコピー
    im = make_graph()
    if not im: return
    W, H = im.size
    
    im.save(FILE_PATH.with_stem(FILE_PATH.stem + "_graph").with_suffix(".png"))
    
    with NamedTemporaryFile(suffix='.png', delete=True) as tmp:
        im.resize((W // 2, H // 2)).save(tmp.name)
        ui_img = ui.Image(str(tmp.name))
        clipboard.set_image(ui_img)
 
    if APPEX:
        show_preview(ui_img)
        appex.finish()
    else:
        im.show()
#-------------------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
