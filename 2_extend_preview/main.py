from fasthtml.common import *
from os import listdir, remove
from os.path import isfile, join, isdir
import mimetypes 
import json
import os
import datetime
import fnmatch
import urllib

if len(sys.argv) > 1:
    base_dir = os.path.abspath(sys.argv[1])
else:
    base_dir = os.getcwd()
print(f"Serving {base_dir}")

app = FastHTML(hdrs=(
    Link(rel='stylesheet', href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css')
))
rt = app.route

@rt("/app.css")
def get(): 
    return FileResponse(f'./public/app.css')

def get_file_info(file_path):
    try:
        stats = os.stat(file_path)
        size = stats.st_size
        # Try to get creation time, fall back to modification time
        try:
            creation_time = datetime.datetime.fromtimestamp(stats.st_birthtime)
        except AttributeError:
            # Some systems don't have st_birthtime, use st_mtime instead
            creation_time = datetime.datetime.fromtimestamp(stats.st_mtime)
        
        # Get file type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            file_type = mime_type.split('/')[-1].upper()
        else:
            file_type = os.path.splitext(file_path)[1][1:].upper() or "Unknown"
        
        return size, creation_time, file_type
    except OSError:
        return None, None, None

def format_date(date):
    if date is None:
        return "-"
    now = datetime.datetime.now()
    if date.date() == now.date():
        return f"Today, {date.strftime('%I:%M %p')}"
    elif date.year == now.year:
        return date.strftime("%d %b, %I:%M %p")
    else:
        return date.strftime("%d %b %Y, %I:%M %p")

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

def search_files(base_path, search_term):
    matches = []
    for root, dirnames, filenames in os.walk(base_path):
        for filename in fnmatch.filter(filenames, f'*{search_term}*'):
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, base_path)
            matches.append(('file', filename, relative_path))
        for dirname in fnmatch.filter(dirnames, f'*{search_term}*'):
            full_path = os.path.join(root, dirname)
            relative_path = os.path.relpath(full_path, base_path)
            matches.append(('folder', dirname, relative_path))
    return matches

def get_file_icon(item):
    if item[0] == 'folder':
        return 'fa-folder'
    else:
        return 'fa-file'

def guess_type_from_content(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type is None:
        try:
            # Check file extension first
            if file_path.lower().endswith(('.log', '.txt', '.csv', '.md')):
                return 'text/plain'
            # Add JSON detection
            if file_path.lower().endswith('.json'):
                return 'application/json'
            
            with open(file_path, 'rb') as f:
                file_head = f.read(256)  # Read first 256 bytes
            
            # Check if content is printable ASCII
            if all(32 <= byte <= 126 or byte in (9, 10, 13) for byte in file_head):
                return 'text/plain'
            with open(file_path, 'rb') as f:
                file_head = f.read(256)  # Read first 256 bytes
            
            # Check for common file signatures
            if file_head.startswith(b'\xFF\xD8\xFF'):
                mime_type = 'image/jpeg'
            elif file_head.startswith(b'\x89PNG\r\n\x1a\n'):
                mime_type = 'image/png'
            elif file_head.startswith(b'GIF87a') or file_head.startswith(b'GIF89a'):
                mime_type = 'image/gif'
            elif file_head.startswith(b'%PDF'):
                mime_type = 'application/pdf'
            elif file_head.startswith(b'PK\x03\x04'):
                mime_type = 'application/zip'
            # Add more file signatures as needed
            
            # If still unknown, use a generic binary type
            if mime_type is None:
                mime_type = 'application/octet-stream'
        
        except IOError:
            mime_type = 'application/octet-stream'
    
    return mime_type

@rt("/image/{path:path}")
async def get(path: str):
    # Decode the URL-encoded path
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(base_dir, decoded_path))
    
    if not full_path.startswith(base_dir):
        return Response("Access denied: Path is outside the allowed directory.", status_code=403)

    if not os.path.isfile(full_path):
        return Response("File not found", status_code=404)

    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type or not mime_type.startswith('image/'):
        return Response("Not an image file", status_code=400)

    return FileResponse(full_path, media_type=mime_type, filename=os.path.basename(full_path))

def get_file_content(file_path):
    mime_type = guess_type_from_content(file_path)
    file_name = os.path.basename(file_path)
    
    if mime_type:
        if mime_type == 'application/json':
            try:
                with open(file_path, 'r') as file:
                    content = json.load(file)
                return file_name, mime_type, json.dumps(content, indent=2)
            except json.JSONDecodeError:
                return file_name, mime_type, "Invalid JSON file"
        elif mime_type.startswith('text/'):
            with open(file_path, 'r') as file:
                return file_name, mime_type, file.read()
        elif mime_type.startswith('image/'):
            return file_name, mime_type, file_path  # Return the file path for images
    
    return file_name, mime_type, None

def render_preview(file_path):
    file_name, mime_type, content = get_file_content(file_path)
    
    preview_content = None
    
    if content is not None:
        if mime_type.startswith('image/'):
            # Use URL encoding for the file path to handle special characters
            encoded_path = urllib.parse.quote(os.path.relpath(file_path, base_dir))
            preview_content = Div(cls='image-container')(
                Img(src=f"/image/{encoded_path}")
            )
        elif mime_type == 'application/json':
            preview_content = Pre(content)
        elif mime_type.startswith('text/'):
            preview_content = Pre(content)
        # Add more MIME type handlers here as needed
    
    if preview_content:
        return Div(cls='file-preview w-full h-full')(
            H3(file_name),
            preview_content
        )
    else:
        return Div(cls='file-preview w-full h-full')(
            H3(file_name),
            P(f"Preview not available for this file type: {mime_type}")
        )

def render_file_list(tree, current_path):
    return Div()(
        Table(cls='w-full table-fixed border-collapse')(
            Thead(
                Tr()(
                    Th("Name", ),
                    Th("Size", ),
                    Th("Kind", ),
                    Th("Date Added", ),
                    # Th("Actions", )
                ),
            ),
            Tbody()(
                *[Tr(
                    Td(
                        Div(cls='flex items-center space-x-2')(
                            I(cls=f'fas {get_file_icon(item)} text-gray-400 flex-shrink-0'),
                            Div(cls='truncate')(
                                A(item[1], 
                                  href=f'/{os.path.relpath(item[2], os.getcwd())}' if item[0] == 'folder' else '#',
                                  onclick=f"showPreview('{os.path.relpath(item[2], os.getcwd())}')" if item[0] == 'file' else None,
                                  cls='text-gray-900 hover:text-blue-600')
                            )
                        ),
                        cls='p-3'
                    ),
                    Td(format_size(get_file_info(item[2])[0]), cls='p-3 text-right text-gray-500 text-sm'),
                    Td(Div(get_file_info(item[2])[2] or "Unknown", cls='truncate'), cls='p-3 text-left text-gray-500 text-sm'),
                    Td(Div(format_date(get_file_info(item[2])[1]), cls='truncate'), cls='p-3 text-right text-gray-500 text-sm'),
                    cls='hover:bg-gray-50'
                ) for item in tree]
            )
        )
    )


def build_tree(path):
    if os.path.isfile(path):
        # If it's a file, return a list with just this file
        return [('file', os.path.basename(path), path)]
    
    tree = []
    for item in sorted(os.listdir(path)):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            tree.append(('folder', item, item_path))
        else:
            tree.append(('file', item, item_path))
    return tree

@rt("/")
@rt("/{path:path}")
def get(path: str = '', search: str = '', container:bool = False):
    # base_dir = os.getcwd()
    full_path = os.path.normpath(os.path.join(base_dir, path))
    breadcrumb_items = [
        A('~', href='/'),
        *[Span('/') +  A(part, href=f'/{"/".join(path.split("/")[:i+1])}')
          for i, part in enumerate(path.split('/')) if part]
    ]
    
    if not full_path.startswith(base_dir):
        return Titled("Access Denied", P("Access denied: Path is outside the allowed directory."))

    try:
        if search:
            tree = search_files(full_path, search)
        elif os.path.isfile(full_path):
            # If it's a file, render the preview directly
            return Titled("File Preview", render_preview(full_path))
        else:
            tree = build_tree(full_path)
        file_list = render_file_list(tree, path)

        # If it's a search request, return only the file list
        if search or container:
            return file_list

        return Title("File System Interface"), Div()(
            # Sidebar
            Div()(
                Div()(
                    Input(type="text",
                        placeholder="Search files...",
                        hx_get=f"/{path}?container=True", hx_trigger="keyup changed delay:200ms", 
                        hx_target="#file-list-container",
                        name="search"),
                ),
                Div()(
                    Div("All", ),
                    Div("Local", ),
                    Div("FTP", ),
                    Div("S3", )
                )
            ),
            # Main content
            Div()(
                # Breadcrumb
                Div()(
                    Div()(*breadcrumb_items)
                ),
                # File list and Preview area
                Div()(
                    # File list
                    Div()(
                        Div(id="file-list-container", )(
                            file_list
                        )
                    ),
                    # Preview area
                    Div()(
                        Div(id='preview-area', )(
                            P("Select a file to preview", )
                        )
                    )
                )
            ),
            Script("""
                function showPreview(path) {
                    fetch(`/${path}?preview=true`)
                        .then(response => response.text())
                        .then(html => {
                            document.getElementById('preview-area').innerHTML = html;
                        });
                }
            """)
        )
    except FileNotFoundError:
        return Titled("Path Not Found", P(f"Path not found: {path}"))

@rt("/{path:path}")
def get(path: str, preview: bool = False):
    base_dir = os.getcwd()
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    if not full_path.startswith(base_dir):
        return Div('Access denied: Path is outside the allowed directory.', cls='error')

    if not os.path.exists(full_path):
        return Div(f'File not found: {path}', cls='error')

    if preview:
        if os.path.isfile(full_path):
            return render_preview(full_path)
        return Div('Preview is only available for files.', cls='error')

    # Existing logic for directory listing
    tree = build_tree(full_path)
    file_list = render_file_list(tree, path)

@rt("/{path:path}", methods=['DELETE'])
async def delete(path: str):
    base_dir = os.getcwd()
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    if not full_path.startswith(base_dir):
        return Div('Access denied: Path is outside the allowed directory.', cls='error')

    if os.path.isfile(full_path):
        os.remove(full_path)
        return RedirectResponse('/', status_code=303)
    return Div('Only files can be deleted.', cls='error')

serve()