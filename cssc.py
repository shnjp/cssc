#!/usr/bin/env python
# encoding: utf-8
"""
cssc.py

Created by shn@glucose.jp on 2009-06-05.
Copyright (c) 2010. All rights reserved.
"""

import sys
import os
from pyparsing import *
import jinja2
import re
import json


# CCS3
CCS3_PROPERTIES = set([
    u'border-radius',
    u'border-top-left-radius',
    
    u'background-size',
    u'background-clip',
    u'background-origin',
    
    u'text-shadow',
    u'box-shadow',
    
    u'column-count',
    u'column-gap',
    u'column-rule',
    u'column-width',
])


# jinja2 
sprite_coords = {}

def jinja_sprite_background(sprite_name, image_name, repeat='no-repeat'):
    s = sprite_coords[sprite_name]
    coord = s['coordinates'][image_name]
    return 'url(%s) %s -%dpx -%dpx' % (
        s['url'], repeat, coord[0], coord[1]
    )


class Renderable(object):
    pass


class Declaration(Renderable):
    @classmethod
    def action(cls, s, loc, tok):
        tokens = tok.asList()
        return cls(tokens[0], tokens[1:])
        
    def __init__(self, property, values):
        self.property = property
        self.values = values
    
    def clone(self):
        return Declaration(self.property, self.values[:])
    
    def render(self, options, output):
        s = u'\t%s: %s;\n' % (self.property, ' '.join(self.values))
        output.write(s.encode('utf8'))
        
        if options.css3:
            if self.property in CCS3_PROPERTIES:
                output.write('\t-moz-%s: %s;\n' % (self.property, ' '.join(self.values)))
                output.write('\t-webkit-%s: %s;\n' % (self.property, ' '.join(self.values)))

    
class Selector(object):
    @classmethod
    def action(cls, s, loc, tok):
        return cls(tok)
        
    def __init__(self, tok):
        self.tok = [''.join(x) for x in tok.asList()]
        self.tok = tok.asList()
    
    def __str__(self):
        return ' '.join(''.join(x) for x in self.tok)
    
    def __repr__(self):
        return '<Selector (%r)>' % self.tok


class RuleSet(Renderable):
    def __init__(self, selectors, declarations):
        """docstring for __init__"""
        self.selectors = selectors
        self.declarations = []
        self.child_rules = []
        
        for x in declarations:
            if isinstance(x, Declaration):
                self.declarations.append(x)
            if isinstance(x, RuleSet):
                self.child_rules.append(x)

    def render(self, options, output):
        return self._render(options, output, [''])
                
    def _render(self, options, output, parent_selectors):
        selectors = []
        for parent in parent_selectors:
            for child in self.selectors:
                child = str(child)
                if child.startswith('_'):
                    s = parent + child[1:]
                else:
                    s = ('%s %s' % (parent, child)).strip()
                selectors.append(s)
        
        output.write(u'%s {\n' % ', '.join(selectors))
        for dec in self.declarations:
            dec.render(options, output)
        output.write(u'}\n')
        
        # render children
        for child in self.child_rules:
            child._render(options, output, selectors)
    
    def __repr__(self):
        return '<RuleSet "%s": %s>' % (', '.join(str(x) for x in self.selectors), self.declarations)

    def iter_tree(self):
        yield self
        for child in self.child_rules:
            for x in child.iter_tree():
                yield x


class Media(Renderable):
    @classmethod
    def action(cls, s, loc, tok):
        tokens = tok.asList()
        medianame = tokens.pop(0).rstrip()
        return cls(medianame, tokens)

    def __init__(self, media, styles):
        self.media = media
        self.styles = styles

    def render(self, options, output):
        output.write('@media %s {\n' % self.media)
        
        for style in self.styles:
            style.render(options, output)
        
        output.write('}\n\n')


class WebkitKeyframes(Renderable):
    @classmethod
    def action(cls, s, loc, tok):
        tokens = tok.asList()
        name = tokens.pop(0).rstrip()
        return cls(name, tokens)

    def __init__(self, name, styles):
        self.name = name
        self.styles = styles

    def render(self, options, output):
        output.write('@-webkit-keyframes %s {\n' % self.name)

        for style in self.styles:
            style.render(options, output)

        output.write('}\n\n')


class Keyframe(Renderable):
    @classmethod
    def action(cls, s, loc, tok):
        tokens = tok.asList()
        return cls(tokens[0], tokens[1])

    def __init__(self, frame, decs):
        self.frame = frame
        self.declarations = decs

    def render(self, options, output):
        output.write(self.frame)
        output.write(' {\n')
        for dec in self.declarations:
            dec.render(options, output)
        output.write('}\n')


###
class CSSCParser(object):
    rex = {
        'nmstart':  '[a-z\200-\377]',
        'nmchar':   '[a-z0-9-\200-\377]'
    }
    #IDENT = ident = Regex('%(nmstart)s%(nmchar)s*' % rex, re.I)
    #IDENT = Regex(r'[a-z0-9_.+-]+', re.I)
    IDENT = Regex(r'[a-z0-9_.+-]+(\s+[a-z0-9_.+-]+)*', re.I)
    STRING = quotedString
    HASH = Regex('#%(nmchar)s*' % rex, re.I)
    URI = Regex(r'url\(\s*([^\s)]*)\s*\)')
    
    combinator = Regex(r'(\+|>\s+)')# oneOf("+ >")
    def combinator_action(s, loc, tok):
        return tok.asList()[0][0]
    combinator.setParseAction(combinator_action)
        
    simple_selector = Regex(r'\*|(_?[a-z0-9#:_=\[\]\-\.]+)|_', re.I)
    selector = OneOrMore(Optional(combinator) + simple_selector)
    selector.setName('selector')
    selector.setParseAction(Selector.action)

    selectors = Group(selector + ZeroOrMore(Suppress(",") + selector))
    
    #variable = Suppress('{{') + IDENT + Suppress('}}')
    
    VALUE = Regex(r'(-|\+)?(\d*\.\d+|\d+)(em|ex|px|cm|mm|in|pt|pc|deg|rad|grad|ms|s|Hz|kHz|%)?(/(-|\+)?(\d*\.\d+|\d+)(em|ex|px|cm|mm|in|pt|pc|deg|rad|grad|ms|s|Hz|kHz|%))?', re.I)
    property_ = IDENT
    term = Forward()
    FUNCTION = IDENT + Suppress('(') + term + ZeroOrMore(Suppress(',') + term) + Suppress(')')
    term << (VALUE | URI | HASH | FUNCTION | STRING | IDENT)
    expr = term + ZeroOrMore((oneOf("/ ,") | Empty()) + term)
    prio = Regex('!\\s*important', re.I)
    
    ruleset = Forward()
    
    def function_action(s, loc, tok):
        tok = tok.asList()
        return '%s(%s)' % (tok[0], ', '.join(tok[1:]))
    FUNCTION.setParseAction(function_action)
    
    declaration_base = property_ + Suppress(':') + expr + Optional(prio)
    declaration_base.setParseAction(Declaration.action)
    
    declaration = ruleset | declaration_base
    declarations = Group(ZeroOrMore(declaration + ZeroOrMore(Suppress(';'))))
    declarations.setName('declarations')
    
    ruleset << selectors + Suppress("{") + declarations + Suppress("}")
    ruleset.setName('ruleset')

    def ruleset_action(s, loc, tok):
        selectors, declarations = tok.asList()
        return RuleSet(selectors, declarations)
    ruleset.setParseAction(ruleset_action)
    
    media = Literal('@media').suppress() + Regex(r'[^{]+') + Suppress("{") + ZeroOrMore(ruleset) + Suppress("}")
    media.setParseAction(Media.action).setName('media')
    
    # @-webkit-keyframes
    frame_identifier = Regex('from|to|\d+%')
    keyframe = frame_identifier + Suppress('{') + \
        Group(ZeroOrMore(declaration_base + ZeroOrMore(Suppress(';')))) + \
        Suppress('}')
    keyframe.setParseAction(Keyframe.action)
    
    webkit_keyframes = Literal('@-webkit-keyframes').suppress() + Regex(r'[^{]+') + Suppress("{") + ZeroOrMore(keyframe) + Suppress("}")
    webkit_keyframes.setParseAction(WebkitKeyframes.action).setName('webkit_keyframes')
    
    css = ZeroOrMore(media | webkit_keyframes | OneOrMore(ruleset))
    cssComment = cppStyleComment 
    css.ignore(cssComment)
            
    def __init__(self):
        """docstring for __init__"""
        pass
    
    def parseString(self, txt):
        """docstring for parseString"""
        import pprint
        results = self.css.parseString(txt, parseAll=True)
        return results.asList()
    
    def parseFile(self, fp):
        """docstring for parseFile"""
        return self.parseString(fo.read())


# TEST
cls = CSSCParser
def test():
    def t(g, t, s):
        print '%r == %r' % (t.parseString(s, parseAll=True), g)

    print cls.FUNCTION.parseString('-webkit-gradient(linear, left top, left bottom, from(#cae5fe), to(#aacff2))', parseAll=True)
    print cls.VALUE.parseString('62.5%', parseAll=True)
    print cls.simple_selector.parseString('a:hover')
    print cls.simple_selector.parseString('_:hover')
    t(['#ss-logo'], cls.simple_selector, '#ss-logo')
    print cls.selector.parseString('.disabled a', parseAll=True)
    print cls.selector.parseString('.site-header > #copyright')
    print cls.selectors.parseString('h1:hover, h2:hover, h3:hover', parseAll=True)
    print cls.selectors.parseString('> label')
    print cls.term.parseString('100em')
    print cls.expr.parseString('#fff url(/static/img/bg/bg_map_04_brue_middle.png) top center repeat-x')
    print cls.declaration.parseString('filter: alpha(opacity=30)')
    print cls.declaration.parseString('margin-left: 10px !important')
    print cls.declaration.parseString('font: 83%/1.4 Sans-Serif')
    print cls.declarations.parseString('font-size: 10%;')
    print cls.declarations.parseString('font-size: 12pt; border: 1px solid none;')
    print cls.ruleset.parseString('textarea {}')
    print cls.expr.parseString('-9999px', parseAll=True)
    print cls.selector.parseString('_ > div', parseAll=True)
    print cls.selector.parseString('input[type=text]', parseAll=True)
    print cls.selectors.parseString('input[type=text], input[type=password]', parseAll=True)
    print cls.css.parseString('@media screen { body { background: blue; }}', parseAll=True)
    t(['10px/30px'], cls.expr, '10px/30px')
    t([''], cls.webkit_keyframes, '''@-webkit-keyframes appear {
        0% {
            opacity: 0.0;
        }
        100% {
            opacity: 1.0;
        }
    }''')
    sys.exit(-1)

### 
def parse_args():
    from optparse import OptionParser
    
    parser = OptionParser()
    parser.add_option("--test", dest="test", default=False,
        action='store_true', help="run tests")
    parser.add_option("-v", dest="variables",
                      help="variable definitions (JSON)", metavar="FILE")
    parser.add_option("-o", dest="output",
                      help="Output file name", metavar="FILE")
    parser.add_option('--coords', action='append')
    parser.add_option("--css3", dest="css3", default=False,
        action="store_true",
        help="Convert CSS3 vendor custom properties")

    options, args = parser.parse_args()
    return options, args

def main():
    options, args = parse_args()
    
    if options.test:
        test()
        return    
    
    variables = {}
    
    if options.variables:
        with open(options.variables, 'rb') as fp:
            for k, v in json.load(fp).iteritems():
                if isinstance(k, unicode):
                    k = k.encode('utf8')
                variables[k] = v
    
    # load sprite coordinates
    if options.coords:
        for coords_def in options.coords:
            coords_name, url = coords_def.split(',', 1)
            key = os.path.splitext(os.path.basename(coords_name))[0]
            sprite_coords[key] = {
                'url': url,
                'coordinates': json.load(open(coords_name, 'r'))
            }
    
    middle = None
    
    # jinja2 setup
    loader = jinja2.FileSystemLoader([os.path.dirname(path) for path in args])
    env = jinja2.Environment(loader=loader,
        extensions=['jinja2.ext.ExprStmtExtension'])
    env.globals.update({
        'sprite_background': jinja_sprite_background
    })

    parser = CSSCParser()
    rules = []
    for path in args:
        t = env.get_template(os.path.basename(path))
        cssbody = t.render(variables)
        if middle:
            middle.write(cssbody.encode('utf-8'))
            middle.write('\n')
        
        try:
            rules.extend(parser.parseString(cssbody))
        except ParseException, exc:
            import traceback
            traceback.print_exc()
            
            print >>sys.stderr, 'exception at : `%s`' % exc.markInputline('')
            raise
            
    if options.output:
        output = open(options.output, 'wb')
    else:
        output = sys.stdout
    
    for rule in rules:
        rule.render(options, output)
        
if __name__ == '__main__':
    main()

