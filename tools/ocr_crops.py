import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from PIL import Image
from tools.capture_and_calibrate import run_ocr

def check_crops():
    img_path = Path("resource/base/image/warehouse_screen.png")
    if not img_path.exists():
        print("Image not found")
        return
    im = Image.open(img_path)

    print("=== Bottom Bar OCR [0, 1450, 2560, 1600] ===")
    crop_bottom = im.crop((0, 1450, 2560, 1600))
    res_b = run_ocr(crop_bottom)
    for r in res_b:
        print(f"  [{r['box'][0]:4d}, {r['box'][1]+1450:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] {r['text']}")

    print("\n=== Top Warehouse Bar OCR [1500, 80, 2560, 250] ===")
    crop_top = im.crop((1500, 80, 2560, 250))
    res_t = run_ocr(crop_top)
    for r in res_t:
        print(f"  [{r['box'][0]+1500:4d}, {r['box'][1]+80:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] {r['text']}")

    print("\n=== Warehouse Column Area OCR [1500, 200, 2560, 1500] ===")
    crop_mid = im.crop((1500, 200, 2560, 1500))
    res_m = run_ocr(crop_mid)
    for r in res_m:
        print(f"  [{r['box'][0]+1500:4d}, {r['box'][1]+200:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] {r['text']}")

def inspect_files(names):
    for name in names:
        p = Path("resource/base/image") / name
        if not p.exists():
            continue
        im = Image.open(p)
        print(f"=== {name} ({im.size}) ===")
        res = run_ocr(im)
        for r in res:
            print(f"  {r['box']} score={r['score']:.2f} | {r['text']}")

def dump_sorted(image_path):
    p = Path(image_path)
    im = Image.open(p)
    res = run_ocr(im)
    res.sort(key=lambda r: (r['box'][1], r['box'][0]))
    print(f"=== All {len(res)} OCR items in {p.name} (sorted by Y, X) ===")
    for r in res:
        print(f"  [{r['box'][0]:4d}, {r['box'][1]:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] score={r['score']:.2f} | {r['text']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        dump_sorted(sys.argv[2])
    elif len(sys.argv) > 1:
        inspect_files(sys.argv[1:])
    else:
        check_crops()
