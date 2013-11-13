#! /usr/bin/python

# PyGreen
# Copyright (c) 2013, Nicolas Vanhoren
# 
# Released under the MIT license
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
# AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import unicode_literals, print_function

import flask
import os.path
from mako.lookup import TemplateLookup
import os
import os.path
import wsgiref.handlers
import sys
import logging
import re
import argparse
import sys
import markdown
import waitress

_logger = logging.getLogger(__name__)

class PyGreen:

    def __init__(self):
        # the Bottle application
        self.app = flask.Flask(__name__)
        # a set of strings that identifies the extension of the files
        # that should be processed using Mako
        self.template_exts = set(["html"])
        # the folder where the files to serve are located. Do not set
        # directly, use set_folder instead
        self.folder = "."
        # the TemplateLookup of Mako
        self.templates = TemplateLookup(directories=[self.folder],
            imports=["from markdown import markdown"],
            input_encoding='iso-8859-1',
            collection_size=100,
            )
        # A list of regular expression. Files whose the name match
        # one of those regular expressions will not be outputed when generating
        # a static version of the web site
        self.file_exclusion = [r".*\.mako", r".*\.py", r"(^|.*\/)\..*"]
        def is_public(path):
            for ex in self.file_exclusion:
                if re.match(ex,path):
                    return False
            return True
            
        def base_lister():
            files = []
            for dirpath, dirnames, filenames in os.walk(self.folder):
                for f in filenames:
                    absp = os.path.join(dirpath, f)
                    path = os.path.relpath(absp, self.folder)
                    if is_public(path):
                        files.append(path)
            return files
        # A list of functions. Each function must return a list of paths
        # of files to export during the generation of the static web site.
        # The default one simply returns all the files contained in the folder.
        # It is necessary to define new listers when new routes are defined
        # in the Bottle application, or the static site generation routine
        # will not be able to detect the files to export.
        self.file_listers = [base_lister]

        def file_renderer(path):
            if is_public(path):
                if path.split(".")[-1] in self.template_exts and self.templates.has_template(path):
                    t = self.templates.get_template(path)
                    data = t.render_unicode(pygreen=self)
                    return data.encode(t.module._source_encoding)
                return flask.send_from_directory(self.folder, path)
            flask.abort(404)
        # The default function used to render files. Could be modified to change the way files are
        # generated, like using another template language or transforming css...
        self.file_renderer = file_renderer
        self.app.add_url_rule('/', "root", lambda: self.file_renderer('index.html'), methods=['GET', 'POST', 'PUT', 'DELETE'])
        self.app.add_url_rule('/<path:path>', "all_files", lambda path: self.file_renderer(path), methods=['GET', 'POST', 'PUT', 'DELETE'])

    def set_folder(self, folder):
        """
        Sets the folder where the files to serve are located.
        """
        self.folder = folder
        self.templates.directories[0] = folder

    def run(self, host='0.0.0.0', port=8080):
        """
        Launch a development web server.
        """
        waitress.serve(self, host=host, port=port)

    def get(self, path):
        """
        Get the content of a file, indentified by its path relative to the folder configured
        in PyGreen. If the file extension is one of the extensions that should be processed
        through Mako, it will be processed.
        """
        data = self.app.test_client().get("/%s" % path).data
        return data

    def gen_static(self, output_folder):
        """
        Generates a complete static version of the web site. It will stored in 
        output_folder.
        """
        files = []
        for l in self.file_listers:
            files += l()
        for f in files:
            _logger.info("generating %s" % f)
            content = self.get(f)
            loc = os.path.join(output_folder, f)
            d = os.path.dirname(loc)
            if not os.path.exists(d):
                os.makedirs(d)
            with open(loc, "wb") as file_:
                file_.write(content)

    def __call__(self, environ, start_response):
        return self.app(environ, start_response)

    def cli(self, cmd_args=None):
        """
        The command line interface of PyGreen.
        """
        logging.basicConfig(level=logging.INFO, format='%(message)s')

        parser = argparse.ArgumentParser(description='PyGreen, micro web framework/static web site generator')
        subparsers = parser.add_subparsers(dest='action')

        parser_serve = subparsers.add_parser('serve', help='serve the web site')
        parser_serve.add_argument('-p', '--port', type=int, default=8080, help='folder containg files to serve')
        parser_serve.add_argument('-f', '--folder', default=".", help='folder containg files to serve')
        parser_serve.add_argument('-d', '--disable-templates', action='store_true', default=False, help='just serve static files, do not use invoke Mako')
        def serve():
            if args.disable_templates:
                self.template_exts = set([])
            self.run(port=args.port)
        parser_serve.set_defaults(func=serve)

        parser_gen = subparsers.add_parser('gen', help='generate a static version of the site')
        parser_gen.add_argument('output', help='folder to store the files')
        parser_gen.add_argument('-f', '--folder', default=".", help='folder containg files to serve')
        def gen():
            self.gen_static(args.output)
        parser_gen.set_defaults(func=gen)

        args = parser.parse_args(cmd_args)
        self.set_folder(args.folder)
        print(parser.description)
        print("")
        args.func()

pygreen = PyGreen()

if __name__ == "__main__":
    pygreen.cli()
