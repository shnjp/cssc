#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
yamlで書かれた段組を読み込んで、CSS Spriteを作成する。
"""
__version__ = '0.1'
__author__ = 'shn@glucose.jp'

#
import sys, os
import yaml
import PIL.Image

basedir = None

S_HORIZONTAL = 'horizontal'

HORIZONTAL = 0
VERTICAL = 1

class SpriteBase(object):
    def __init__(self, parent):
        self.parent = parent
        self.topleft = None
    
    def set_topleft(self, tl):
        self.topleft = tl
    
    # 
    def make_position(self):
        pass
    
class Sprite(SpriteBase):
    def __init__(self, parent, filename, image):
        super(Sprite, self).__init__(parent)

        self.filename = filename
        self.image = image
    
    def get_size(self):
        return self.image.size
    size = property(get_size)
    
    def build_image(self):
        return self.image
    
class SpriteSet(SpriteBase):
    def __init__(self, parent, direction):
        assert direction in (HORIZONTAL, VERTICAL)
        super(SpriteSet, self).__init__(parent)
        
        self.direction = direction
        self.sprites = []
        self.size = None
    
    def add_image(self, image):
        #assert isinstance(image, SpriteBase)
        self.sprites.append(image)
    
    def make_position(self):
        # calc sprite size
        get_size_f = lambda x: x
        if self.direction == VERTICAL:
            get_size_f = lambda x: (x[1], x[0])
        
        corner = 0
        max_size = 0
        for sprite in self.sprites:
            sprite.make_position()
            
            if self.direction == HORIZONTAL:
                tl = corner, 0
            else:
                tl = 0, corner
            sprite.set_topleft(tl)
            
            # next
            pri, sec = get_size_f(sprite.size)
            corner += pri
            max_size = max(max_size, sec)
        
        if self.direction == HORIZONTAL:
            self.size = corner, max_size
        else:
            self.size = max_size, corner

    def build_image(self):
        image = PIL.Image.new('RGBA', self.size, 0x000000FF)
        
        for sprite in self.sprites:
            tl = sprite.topleft
            sz = sprite.size
            bounds = (tl[0], tl[1], tl[0] + sz[0], tl[1] + sz[1])
            image.paste(sprite.build_image(), bounds)
        return image

    def dump_coords(self, base_topleft=(0, 0)):
        result = []
        for sprite in self.sprites:
            tl = base_topleft[0] + sprite.topleft[0], base_topleft[1] + sprite.topleft[1]
            if isinstance(sprite, SpriteSet):
                result.extend(sprite.dump_coords(tl))
            else:
                result.append((sprite.filename, (tl[0], tl[1])))
        return result

class ImageLoader(object):
    def __init__(self, base_dir='.'):
        self.base_dir = base_dir
    
    def load(self, yamlfile):
        sprite = self.load_sprite(None, yaml.load(open(yamlfile)))
        sprite.make_position()
        
        return sprite
    
    def load_sprite(self, parent, dataset):
        assert parent is None or isinstance(parent, SpriteSet)
        
        if isinstance(dataset, str):
            # is sprite image file name.
            image = PIL.Image.open(os.path.join(self.base_dir, dataset))
            return Sprite(parent, dataset, image)
        elif isinstance(dataset, dict):
            # is sprite set
            assert 'images' in dataset
            
            direction = HORIZONTAL if dataset.get('direction', S_HORIZONTAL) == S_HORIZONTAL else VERTICAL
            imagelist = dataset['images']
            
            return self.load_sprite_set(parent, direction, imagelist)
        elif isinstance(dataset, list):
            # is sprite set by simple alsfjleaflasef. inverted direction of parent
            direction = HORIZONTAL
            if parent:
                direction = 1 - parent.direction
            return self.load_sprite_set(parent, direction, dataset)

    def load_sprite_set(self, parent, direction, imagelist):
        ss = SpriteSet(parent, direction)
        for dataset in imagelist:
            ss.add_image(self.load_sprite(ss, dataset))
        return ss

###
def build_sprite(yamlfile, output_file='sprite.png', base_dir='.', coordinate_file=None):
    sprite = ImageLoader(base_dir).load(yamlfile)
    sprite_image = sprite.build_image()
    sprite_image.save(output_file, 'PNG')
    
    if coordinate_file:
        import json
        json.dump(dict(sprite.dump_coords()), open(coordinate_file, 'w'))
    
def get_options():
    import optparse
    
    parser = optparse.OptionParser(
        usage='%prog [options] YAML_FILE'
    )
    parser.add_option(
        '-o', '--output-file',
        action='store', type='string',
        dest='output_file',
        default='sprite.png',
        help="output sprite image file name. default `sprite.png`"
    )
    parser.add_option(
        '-b', '--base-dir',
        action='store', type='string',
        dest='base_dir',
        default='',
        help="image file's base directory. default current directory"
    )
    parser.add_option(
        '-c', '--coordinate-file',
        action='store', type='string',
        dest='coordinate_file',
        default='sprite.json',
        help="output image coordinates as json format. default 'sprite.json'"
    )
    
    options, args = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit()
    
    return options, args

if __name__ == "__main__":
    options, args = get_options()
    build_sprite(args[0], **options.__dict__)
