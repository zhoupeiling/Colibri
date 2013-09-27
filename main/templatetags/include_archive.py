#
# -*- coding: utf-8
#

from django.template import Node, NodeList, Template, Context, Variable, Library, TemplateSyntaxError, TemplateDoesNotExist
from django.conf import settings
from os.path import abspath

register = Library()


MY_ALLOWED_INCLUDE_ROOTS = ( abspath(settings.ARCHIVE_DIR),)

def include_is_allowed(filepath):
    for root in MY_ALLOWED_INCLUDE_ROOTS:
        if filepath.startswith(root):
            return True
    return False

class include_archiveNode(Node):
    def __init__(self, varname):
        self.varname = Variable(varname)

    def render(self, context):
        # interpret the variable
        try:
            filepath = self.varname.resolve(context)
        except TemplateSyntaxError, e:
            if settings.TEMPLATE_DEBUG:
                raise
            return ''
        except:
            if settings.DEBUG:
                raise
            return '' # Fail silently for invalid included templates.
        # check
        if not include_is_allowed(filepath):
            if settings.DEBUG:
                return "[Didn't have permission to include file]"
            else:
                return '' # Fail silently for invalid includes.
        # load the content
        try:
            fp = open(filepath, 'r')
            output = fp.read()
            fp.close()
        except IOError:
            if settings.DEBUG:
                return "[Error while reading the file]"
            else:
                return ''
        return output

@register.tag
def include_archive(parser, token):
    """
    Outputs the contents of a given file into the page.

    The tag ``ssi`` can not read the filename from a variable
    The tag ``include`` can do that, but can only load from files in
    templates/* directories.

    This tag read the name from the variable given in argument, and include
    the content of this filename.

        {% ssi myfilenamevar %}

    """
    bits = token.contents.split()
    if len(bits)!=2:
        raise TemplateSyntaxError("'include_archive' tag takes one argument: the name of a variable containing the path to"
                                  " the file to be included")
    return include_archiveNode(bits[1])
