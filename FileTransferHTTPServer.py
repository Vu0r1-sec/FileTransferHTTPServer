#!/usr/bin/env python3

__version__ = "0.1"
__all__ = ["FileTransferHTTPRequestHandler"]
__author__ = "Vu0r1"

# This script is based on https://github.com/bones7456/bones7456/blob/master/SimpleHTTPServerWithUpload.py writed by bones7456

import re
import argparse
import os
import html
import sys
import urllib.parse

from io import BytesIO
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, HTTPServer


class FileTransferHTTPRequestHandler(SimpleHTTPRequestHandler):
    verbose = False

    extensions_map = {
        ".py": "text/plain",
        ".c": "text/plain",
        ".cpp": "text/plain",
        ".h": "text/plain",
        ".bat": "text/plain",
        ".ps1": "text/plain",
    }

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """
        try:
            list = os.listdir(path)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path, errors="surrogatepass")
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(self.path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        title = f"Directory listing for {displaypath}"
        r.append("<!DOCTYPE HTML>")
        r.append('<html lang="en">')
        r.append("<head>")
        r.append(f'<meta charset="{enc}">')
        r.append(f"<title>{title}</title>\n</head>")
        r.append(f"<body>\n<h1>{title}</h1>")
        r.append("<hr>\n<ul>")
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            r.append(
                '<li><a href="%s">%s</a></li>'
                % (
                    urllib.parse.quote(linkname, errors="surrogatepass"),
                    html.escape(displayname, quote=False),
                )
            )
        r.append("</ul>\n<hr>\n")
        # Add upload form
        r.append('<form ENCTYPE="multipart/form-data" method="post">')
        r.append('<input name="file" type="file" multiple />')
        r.append('<input type="submit" value="Upload files"/></form>\n')
        r.append("<hr>\n")
        r.append("</body>\n</html>\n")
        encoded = "\n".join(r).encode(enc, "surrogateescape")
        f = BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

    def do_POST(self):
        """Serve POST request"""

        if self.parse_post_data():
            title = "Upload files Success"
            status = HTTPStatus.OK
        else:
            title = "Upload files Failure"
            status = HTTPStatus.BAD_REQUEST

        back = self.headers["referer"] or self.path
        enc = sys.getfilesystemencoding()
        r = []
        r.append("<!DOCTYPE HTML>")
        r.append('<html lang="en">')
        r.append("<head>")
        r.append(f'<meta charset="{enc}">')
        r.append(f"<title>{title}</title>\n</head>")
        r.append(f"<body>\n<h1>{title}</h1>")
        r.append(f'<a href="{back}">back</a>')
        r.append("</body>\n</html>\n")
        encoded = "\n".join(r).encode(enc, "surrogateescape")
        self.send_response(status)
        self.send_header("Content-type", f"text/html; charset={enc}")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def open_stream(self, filename: str):
        absPath = self.translate_path(self.path)
        if filename:
            filePath = os.path.join(absPath, filename)
        else:
            filename = urllib.parse.urlparse(self.path, allow_fragments=False).path
            filePath = absPath

        while os.path.exists(filePath):
            filePath += "_"

        try:
            fs = open(filePath, "wb")
        except IOError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Error on file creation")
            return None

        if self.verbose:
            print(f"BEGIN File '{filename}' => '{filePath}'")
        return (fs, filePath)

    def close_stream(self, fs, preline: str = None):
        if not fs:
            return None

        if preline != None:
            preline = preline[0:-2]
            fs.write(preline)
        fs.close()
        if self.verbose:
            print("END File")

        return None

    def parse_post_data(self):
        content_type = self.headers["content-type"]
        if not "multipart/form-data" in content_type:
            self.log_message('"Invalid content-type"')
            return False
        if self.verbose:
            print("Content-Type : '%s'" % content_type)
        boundaries = re.findall(r"multipart/form-data; boundary=(.*)", content_type)
        if not boundaries:
            self.log_message('"Boundary not found"')
            return False
        boundary = boundaries[0]
        fs = None
        try:
            line = b""
            while True:
                preline = line
                line = self.rfile.readline()
                if not line:
                    break
                # end of datas
                if line == ("--" + boundary + "--\r\n").encode():
                    fs = self.close_stream(fs, preline)
                    if self.verbose:
                        print("END Transmission")
                    return True

                # new data
                if line == ("--" + boundary + "\r\n").encode():
                    fs = self.close_stream(fs, preline)
                    # Content-Disposition
                    line = self.rfile.readline()
                    fn = re.findall(
                        r'Content-Disposition.*name="(.*)"; filename="(.*)"',
                        line.decode(),
                    )
                    if not fn or not fn[0] or not fn[0][1]:
                        self.log_message('"Filename not defined"')
                        return False

                    (fs, filepath) = self.open_stream(fn[0][1])
                    if not fs:
                        return False

                    # Content-type
                    self.rfile.readline()
                    # empty separator
                    self.rfile.readline()
                    line = b""
                    continue

                if fs:
                    fs.write(preline)

                else:
                    self.log_message('"Unexpected line : "' + line.decode() + '"')
            return False
        finally:
            fs = self.close_stream(fs, preline)

    def do_PUT(self):
        """Serve a PUT request."""
        length = int(self.headers["Content-Length"])
        try:
            (out, filepath) = self.open_stream(None)
            if not out:
                return

            out.write(self.rfile.read(length))
        finally:
            out = self.close_stream(out)

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        sys.stderr.write(
            '%s - - [%s] %s "%s" "%s"\n'
            % (
                self.address_string(),
                self.log_date_time_string(),
                format % args,
                self.headers["Referer"],
                self.headers["User-Agent"],
            )
        )

    def version_string(self):
        """Return the server software version string."""
        return "FileTransferHTTPServer/" + __version__


def serve(
    ServerClass=HTTPServer,
    host: str = "0.0.0.0",
    port: int = 8000,
    directory: str = ".",
    verbose: bool = False,
):
    fullPath = os.path.abspath(directory)
    handler = FileTransferHTTPRequestHandler
    handler.verbose = verbose
    server_address = (host, port)
    with ServerClass(server_address, handler) as httpd:
        try:
            # Start the server and keep it running until interrupted
            print(f"Serving HTTP on {host}:{port} for {fullPath} ...")
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down the server...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-H", "--host", default="0.0.0.0", help="Server hostname")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Server port")
    parser.add_argument("-d", "--directory", default=".", help="Root directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    serve(host=args.host, port=args.port, verbose=args.verbose)
