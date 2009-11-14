#!/usr/bin/env python
# encoding: utf-8
"""
cssc.py

Created by shn on 2009-06-05.
Copyright (c) 2009 __MyCompanyName__. All rights reserved.
"""

import sys, os
from pyparsing import *
import jinja2
import re
import json

# jinja2 
sprite_coords = {}

def jinja_sprite_background(sprite_name, image_name):
    s = sprite_coords[sprite_name]
    coord = s['coordinates'][image_name]
    return 'background: url(%s) no-repeat -%dpx -%dpx' % (
        s['url'], coord[0], coord[1]
    )

def renderTemplate(fp, variables={}):
    # TODO　やっつけ
    global jinja_variables
    template = jinja2.Template(fp.read().decode('utf8'))
    jinja_variables = {
        'sprite_background': jinja_sprite_background
    }
    jinja_variables.update(variables)
    return template.render(jinja_variables)

class Declaration(object):
    @classmethod
    def action(cls, s, loc, tok):
        tokens = tok.asList()
        return cls(tokens[0], tokens[1:])
        
    def __init__(self, property, values):
        self.property = property
        self.values = values
    
    def __str__(self):
        return '%s: %s;' % (self.property, ' '.join(self.values))
    
    def clone(self):
        return Declaration(self.property, self.values[:])
    
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

class RuleSet(object):
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
                
    def render(self, output=sys.stdout):
        return self._render(output, [''])
    
    def _render(self, output, parent_selectors):
        selectors = []
        for parent in parent_selectors:
            for child in self.selectors:
                child = str(child)
                if child.startswith('_'):
                    s = parent + child[1:]
                else:
                    s = ('%s %s' % (parent, child)).strip()
                selectors.append(s)
        
        jointer = ', '
        
        o = [jointer.join(selectors), u' {\n']
        for dec in self.declarations:
            o.append(u'\t%s\n' % dec)
        o.append(u'}\n')
        
        output.write(u''.join(o).encode('utf8'))
        
        # render children
        for child in self.child_rules:
            child._render(output, selectors)
    
    def __repr__(self):
        return '<RuleSet "%s": %s>' % (', '.join(str(x) for x in self.selectors), self.declarations)

    def iter_tree(self):
        yield self
        for child in self.child_rules:
            for x in child.iter_tree():
                yield x
        

def iter_rules(rules):
    for rule in rules:
        for x in rule.iter_tree():
            yield x
            

###
class CSSCParser(object):
    rex = {
        'nmstart':  '[a-z\200-\377]',
        'nmchar':   '[a-z0-9-\200-\377]'
    }
    #IDENT = ident = Regex('%(nmstart)s%(nmchar)s*' % rex, re.I)
    IDENT = Regex(r'[a-z0-9_.+-]+', re.I)
    STRING = quotedString
    HASH = Regex('#%(nmchar)s*' % rex, re.I)
    
    URI = Regex(r'url\(\s*([^\s)]*)\s*\)')
    
    combinator = Regex(r'(\+|>\s+)')# oneOf("+ >")
    def combinator_action(s, loc, tok):
        return tok.asList()[0][0]
    combinator.setParseAction(combinator_action)
        
    element_name = IDENT | '*'
    class_ = Regex('\\.%(nmchar)s*' % rex, re.I)
    attrib = IDENT | '*'
    pseudo = Combine(Literal(':') + IDENT)
    attr_selector = Regex(r'\[[^]]*\]' % rex, re.I)
    ss_modifier = Or([HASH, class_, attrib, pseudo, attr_selector])
    simple_selector = Combine((element_name + ZeroOrMore(ss_modifier)) | OneOrMore(ss_modifier))
    selector = simple_selector + ZeroOrMore(Optional(combinator) + simple_selector)
    selector.setName('selector')
    selector.setParseAction(Selector.action)

    selectors = Group(selector + ZeroOrMore(Suppress(",") + selector))
    
    variable = Suppress('{{') + IDENT + Suppress('}}')
    
    VALUE = Regex(r'(-|\+)?(\d*\.\d+|\d+)(em|ex|px|cm|mm|in|pt|pc|deg|rad|grad|ms|s|Hz|kHz|%)?', re.I)
    property_ = IDENT
    FUNCTION = IDENT + Suppress('(') + Regex('[^)]*') + Suppress(')')
    term = VALUE | URI | HASH | FUNCTION | STRING | IDENT
    expr = term + ZeroOrMore((oneOf("/ ,") | Empty()) + term)
    prio = Regex('!\\s*important', re.I)
    
    ruleset = Forward()
    
    def function_action(s, loc, tok):
        tok = tok.asList()
        return '%s(%s)' % (tok[0], ', '.join(tok[1:]))
    FUNCTION.setParseAction(function_action)
    
    declaration = property_ + Suppress(':') + expr + Optional(prio)
    declaration.setParseAction(Declaration.action)
    
    declaration = ruleset | variable | declaration
    declarations = Group(ZeroOrMore(declaration + ZeroOrMore(Suppress(';'))))
    declarations.setName('declarations')
    
    ruleset << selectors + Suppress("{") + declarations + Suppress("}")
    ruleset.setName('ruleset')
    stylesheet = ZeroOrMore(ruleset)
    
    css = stylesheet
    cssComment = cppStyleComment 
    css.ignore(cssComment)
    
    def ruleset_action(s, loc, tok):
        selectors, declarations = tok.asList()
        return RuleSet(selectors, declarations)
    ruleset.setParseAction(ruleset_action)
        
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

# CCS3
CCS3_PROPERTIES = set([
    u'border-radius',
    u'border-top-left-radius'
])

def covert_css3_properties(rules):
    """CSS3のプロパティをベンダ拡張に翻訳する"""
    for rule in iter_rules(rules):
        new_declarations = None
        for idx, decl in enumerate(rule.declarations):
            if isinstance(decl, Declaration):
                if decl.property in CCS3_PROPERTIES:
                    if new_declarations is None:
                        new_declarations = rule.declarations[:idx]
                    
                    for prefix in ['moz', 'webkit']:
                        x = decl.clone()
                        x.property = '-%s-%s' % (prefix, x.property)
                        new_declarations.append(x)
                    
            if new_declarations is not None:
                new_declarations.append(decl)

        if new_declarations is not None:
            rule.declarations = new_declarations
        
# TEST
cls = CSSCParser
if 0:
    print cls.VALUE.parseString('62.5%', parseAll=True)
    print cls.simple_selector.parseString('a:hover')
    print cls.simple_selector.parseString('_:hover')
    print cls.selector.parseString('.disabled a', parseAll=True)
    print cls.selector.parseString('.site-header > #copyright')
    print cls.selectors.parseString('h1:hover, h2:hover, h3:hover')
    print cls.term.parseString('100em')
    print cls.expr.parseString('#fff url(/static/img/bg/bg_map_04_brue_middle.png) top center repeat-x')
    print cls.declaration.parseString('filter: alpha(opacity=30)')
    print cls.declaration.parseString('margin-left: 10px !important')
    print cls.declaration.parseString('font: 83%/1.4 Sans-Serif')
    print cls.declarations.parseString('font-size: 10%;')
    print cls.declarations.parseString('font-size: 12pt; border: 1px solid none;')
    print cls.ruleset.parseString('textarea {}')
    print cls.expr.parseString('-9999px', parseAll=True)
    print 
    print cls.selector.parseString('_ > div', parseAll=True)
    print cls.selector.parseString('input[type=text]', parseAll=True)
    print cls.selectors.parseString('input[type=text], input[type=password]', parseAll=True)
    sys.exit(-1)
    
### 
def parse_args():
    from optparse import OptionParser
    
    parser = OptionParser()
    parser.add_option("-v", dest="variables",
                      help="variable definitions (JSON)", metavar="FILE")
    parser.add_option("-o", dest="output",
                      help="Output file name", metavar="FILE")
    parser.add_option('--coords', action='append')
    parser.add_option("--css3", dest="css3", default=False, action="store_true",
                      help="Convert CSS3 vendor custom properties")

    options, args = parser.parse_args()
    return options, args

def main():
    options, args = parse_args()
    
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
            sprite_coords[coords_name] = {
                'url': url,
                'coordinates': json.load(open(coords_name + '.json', 'r'))
            }
            
    middle = None
    if 1:
        middle = open('dump.cssc', 'w')
    
    parser = CSSCParser()
    rules = []
    for fn in args:
        with open(fn, 'rb') as fp:
            cssbody = renderTemplate(fp, variables=variables)
            if middle:
                middle.write(cssbody)
                middle.write('\n')
            rules.extend(parser.parseString(cssbody))

    if options.output:
        output = open(options.output, 'wb')
    else:
        output = sys.stdout
    
    if options.css3:
        covert_css3_properties(rules)

    for rule in rules:
        rule.render(output)
        
if __name__ == '__main__':
    main()

