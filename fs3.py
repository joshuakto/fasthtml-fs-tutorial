import os
import sys
import mimetypes
import json
import datetime
import fnmatch
import base64
from fasthtml.common import *
from fastapi import Request
from typing import List, Tuple

# Set up base directory
if len(sys.argv) > 1:
    base_dir = os.path.abspath(sys.argv[1])
else:
    base_dir = os.getcwd()
print(f"Serving {base_dir}")

app = FastHTML(hdrs=(
    Link(rel="stylesheet", href="/app.css", type="text/css"),
    Link(rel='stylesheet', href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css')
))
rt = app.route

@rt("/app.css")
def get():
    return FileResponse('./public/app.css')

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

def get_file_info(file_path: str) -> Tuple[int, datetime.datetime, str]:
    try:
        stats = os.stat(file_path)
        size = stats.st_size
        creation_time = datetime.datetime.fromtimestamp(stats.st_mtime)
        mime_type, _ = mimetypes.guess_type(file_path)
        file_type = mime_type.split('/')[-1].upper() if mime_type else os.path.splitext(file_path)[1][1:].upper() or "Unknown"
        return size, creation_time, file_type
    except OSError:
        return 0, datetime.datetime.now(), "Unknown"

def format_date(date: datetime.datetime) -> str:
    now = datetime.datetime.now()
    if date.date() == now.date():
        return f"Today, {date.strftime('%I:%M %p')}"
    elif date.year == now.year:
        return date.strftime("%d %b, %I:%M %p")
    else:
        return date.strftime("%d %b %Y, %I:%M %p")

def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

def search_files(base_path: str, search_term: str) -> List[Tuple[str, str, str]]:
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

def get_file_icon(item_type: str) -> str:
    return 'fa-folder' if item_type == 'folder' else 'fa-file'

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
            with open(file_path, 'rb') as file:
                image_data = base64.b64encode(file.read()).decode('utf-8')
            return file_name, mime_type, f"data:{mime_type};base64,{image_data}"
    
    return file_name, "application/octet-stream", None

def render_preview(file_path: str) -> Div:
    file_name, mime_type, content = get_file_content(file_path)
    
    if content is not None:
        if mime_type.startswith('image/'):
            preview_content = Div(cls='image-container')(
                Img(src=content, cls="max-w-full max-h-[400px] object-contain")
            )
        elif mime_type == 'application/json' or mime_type.startswith('text/'):
            preview_content = Pre(content, cls="bg-gray-100 p-4 rounded-md overflow-auto")
        else:
            preview_content = P(f"Preview not available for this file type: {mime_type}", cls="text-gray-500 italic")
    else:
        preview_content = P(f"Preview not available for this file type: {mime_type}", cls="text-gray-500 italic")

    return Div(cls='file-preview w-full h-full')(
        H3(file_name, cls="text-lg font-semibold mb-2"),
        preview_content
    )

def render_file_list(tree: List[Tuple[str, str, str]], current_path: str) -> Div:
    return Table(cls="flex flex-col h-full")(
        # Fixed header
        Thead(cls="bg-gray-50 sticky top-0 z-10")(
            Tr(cls="flex text-left text-xs font-medium text-gray-500 uppercase tracking-wider")(
                Th("Name", cls="w-2/5 p-3"),
                Th("Size", cls="w-1/6 p-3 text-right"),
                Th("Kind", cls="w-1/6 p-3 text-center"),
                Th("Date Added", cls="w-1/4 p-3 text-right"),
            )
        ),
        # Scrollable content
        Tbody(cls="flex-1 overflow-auto")(
            *[Tr(cls="flex hover:bg-gray-50")(
                Td(cls="w-2/5 p-3 flex items-center space-x-2")(
                    I(cls=f'fas {get_file_icon(item[0])} text-gray-400 flex-shrink-0'),
                    Div(cls='truncate')(
                        A(item[1], 
                        href=f'/{os.path.relpath(item[2], base_dir)}' if item[0] == 'folder' else '#',
                        hx_get=f'/{os.path.relpath(item[2], base_dir)}?preview=true' if item[0] == 'file' else None,
                        hx_target='#preview-area',
                        cls='text-gray-900 hover:text-blue-600')
                        # A(item[1], 
                        #     href=f'/{os.path.relpath(item[2], base_dir)}' if item[0] == 'folder' else '#',
                        #     onclick=f"showPreview('{os.path.relpath(item[2], base_dir)}')" if item[0] == 'file' else None,
                        #     cls='text-gray-900 hover:text-blue-600')
                    )
                ),
                Td(format_size(get_file_info(item[2])[0]), cls='w-1/6 p-3 text-right text-gray-500 text-sm'),
                Td(Div(get_file_info(item[2])[2], cls='truncate'), cls='w-1/6 p-3 text-left text-gray-500 text-sm'),
                Td(Div(format_date(get_file_info(item[2])[1]), cls='truncate'), cls='w-1/4 p-3 text-right text-gray-500 text-sm'),
            ) for item in tree]
        )
    )

def build_tree(path: str) -> List[Tuple[str, str, str]]:
    tree = []
    for item in sorted(os.listdir(path)):
        item_path = os.path.join(path, item)
        relative_path = os.path.relpath(item_path, base_dir)
        if os.path.isdir(item_path):
            tree.append(('folder', item, relative_path))
        else:
            tree.append(('file', item, relative_path))
    return tree

def handle_file(path: str, preview: bool = False):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    mime_type, _ = mimetypes.guess_type(full_path)
    
    if preview:
        return render_preview(full_path)
    else:
        return FileResponse(full_path, media_type=mime_type, filename=os.path.basename(full_path))

def handle_directory(path: str, search: str = ''):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    if search:
        tree = search_files(full_path, search)
    else:
        tree = build_tree(full_path)
    
    return render_file_list(tree, path)

def render_main_page(path: str, file_list: Div):
    breadcrumb_items = [
        A('~', href='/'),
        *[Span('/') +  A(part, href=f'/{"/".join(path.split("/")[:i+1])}')
          for i, part in enumerate(path.split('/')) if part]
    ]

    return Title("File System Interface"), Div(cls="h-screen min-h-screen bg-gray-100 text-gray-900 flex overflow-hidden")(
        # Sidebar
        Div(cls="w-64 bg-white shadow-lg fixed h-full")(
            Div(cls="p-4")(
                Input(type="text", cls="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    placeholder="Search files...",
                    hx_get=f"/{path}", hx_trigger="keyup changed delay:100ms", 
                    hx_target="#file-list-container",
                    hx_push_url="false",
                    name="search"),
            ),
            Div(cls="mt-4")(
                Div("All", cls="px-4 py-2 bg-blue-500 text-white cursor-pointer"),
                Div("Local", cls="px-4 py-2 hover:bg-gray-100 cursor-pointer"),
                Div("FTP", cls="px-4 py-2 hover:bg-gray-100 cursor-pointer"),
                Div("S3", cls="px-4 py-2 hover:bg-gray-100 cursor-pointer")
            )
        ),
        # Main content
        # Div(cls="w-full h-full ml-64 flex flex-col overflow-hidden")(
        Div(cls="ml-64 flex-1 flex flex-col overflow-hidden")(
            # Breadcrumb
            Div(cls="w-full p-4 bg-white shadow-md")(
                Div(cls="text-sm text-gray-600")(*breadcrumb_items)
            ),
            # File list and Preview area
            # Div(cls="h-full flex-grow flex p-6 overflow-hidden")(
            Div(cls="flex-1 flex p-6 space-x-4 overflow-hidden")(
                # File list
                Div(cls="w-3/5 pr-4 h-full max-w-full overflow-auto")(
                    # Div(id="file-list-container", cls="bg-white rounded-lg shadow-md h-[calc(100vh-160px)] overflow-auto")(
                    Div(id="file-list-container", cls="h-full max-h-full flex-1 bg-white rounded-lg shadow-md overflow-hidden")(
                        file_list
                    )
                ),
                # Preview area
                Div(cls="w-2/5 bg-white rounded-lg shadow-md overflow-hidden")(
                    # Div(id='preview-area', cls="h-full p-4 overflow-auto")(
                    Div(id='preview-area', cls="flex-1 p-4 overflow-auto h-full pb-2")(
                        P("Select a file to preview", cls="text-gray-500 italic")
                    )
                )
            )
        ),
    )


@rt("/")
@rt("/{path:path}")
def get(path: str = '', search: str = '', preview: bool = False, hx_request: bool = False):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    if not full_path.startswith(base_dir):
        return Response("Access denied: Path is outside the allowed directory.", status_code=403)

    if not os.path.exists(full_path):
        return Response("Path not found", status_code=404)

    if os.path.isfile(full_path):
        return handle_file(path, preview)
    else:
        file_list = handle_directory(path, search)
        if search or preview or hx_request:
            return file_list
        else:
            return render_main_page(path, file_list)

serve()