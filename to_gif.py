#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
http://nadiana.com/pil-tips-converting-png-gif

PNGをがんばって、できるだけ綺麗にGIFにする
"""

import sys
import random
import PIL.Image

def main(infile, outfile):
    source = PIL.Image.open(infile)
    if source.mode not in ('RGB', 'RGBA'):
        source = source.convert('RGBA')
    
    # maskを作成
    mask = create_mask(source)
    
    # 背景を塗り潰し
    im = PIL.Image.new('RGBA', source.size, (255, 255, 255))
    im.paste(source, source)

    # 透過用の色
    bgcolor = unique_color(source)
    im.paste(bgcolor, mask)

    im = im.convert('RGB').convert('P', palette=PIL.Image.ADAPTIVE)
    im.save(outfile, 'GIF', transparency=color_index(im, bgcolor))

def create_mask(source, threshold=0):
    return PIL.Image.eval(source.split()[-1], lambda x: 255 if x <= threshold else 0)

def unique_color(image):
    """find a color that doesn't exist in the image
    """
    colors = image.getdata()
    while True:
        # Generate a random color
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )
        if color not in colors:
            return color

def color_index(image, color):
    """Find the color index"""
    palette = image.getpalette()
    palette_colors = zip(palette[::3], palette[1::3], palette[2::3])
    return palette_colors.index(color)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])