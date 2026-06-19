# -*- coding: utf-8 -*-
"""og-image.svg のデザインをそのままPNG化する一回限りのスクリプト。
XのカードはSVG非対応なので、フォールバック用に docs/og-image.png を作る。"""
from PIL import Image, ImageDraw, ImageFont

SITE_NAME = "予約開始レーダー"
W, H = 1200, 630
img = Image.new("RGB", (W, H), "#F5F6F8")
d = ImageDraw.Draw(img)

name_font = ImageFont.truetype(r"C:\Windows\Fonts\YuGothB.ttc", 76)
tag_font  = ImageFont.truetype(r"C:\Windows\Fonts\YuGothB.ttc", 34)
sub_font  = ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc", 28)
btn_font  = ImageFont.truetype(r"C:\Windows\Fonts\YuGothB.ttc", 25)

# 白カード
d.rounded_rectangle((72, 70, 72 + 1056, 70 + 490), radius=32,
                    fill="#FFFFFF", outline="#E7E9EF", width=3)
# ロゴ(時計+チェック風)
d.ellipse((190 - 72, 198 - 72, 190 + 72, 198 + 72), fill="#E3F5EE")
d.ellipse((190 - 48, 198 - 48, 190 + 48, 198 + 48), outline="#0BA678", width=12)
d.line((190, 198, 232, 170), fill="#E5304F", width=12)
d.ellipse((190 - 12, 198 - 12, 190 + 12, 198 + 12), fill="#14181F")
# テキスト(SVGはベースライン基準なので anchor="ls")
d.text((300, 205), SITE_NAME, font=name_font, fill="#14181F", anchor="ls")
d.text((304, 282), "ホビーの予約開始を毎日自動キャッチ", font=tag_font, fill="#0BA678", anchor="ls")
d.text((304, 354), "ポケカ / ガンプラ / フィギュア / ゲーム / グッズ", font=sub_font, fill="#707888", anchor="ls")
# ボタン
d.rounded_rectangle((304, 414, 304 + 380, 414 + 62), radius=31, fill="#14181F")
d.text((342, 456), "新着予約をすばやく確認", font=btn_font, fill="#FFFFFF", anchor="ls")

img.save("docs/og-image.png", "PNG")
print("wrote docs/og-image.png", img.size)
