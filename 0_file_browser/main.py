import os
import sys
import mimetypes
import fnmatch
import datetime
from fasthtml.common import *
from fastapi import Request
from typing import List, Tuple

# Set up base directory
if len(sys.argv) > 1:
    base_dir = os.path.abspath(sys.argv[1])
else:
    base_dir = os.getcwd()
print(f"Serving {base_dir}")

app = FastHTML()
rt = app.route

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
    mime_type, _ = mimetypes.guess_type(file_path)
    file_name = os.path.basename(file_path)
    
    if mime_type and mime_type.startswith('text/'):
        with open(file_path, 'r') as file:
            return file_name, mime_type, file.read()
    
    return file_name, mime_type, None

def render_preview(file_path: str) -> Div:
    file_name, mime_type, content = get_file_content(file_path)
    
    if content is not None:
        preview_content = Pre(content)
    else:
        preview_content = P(f"Preview not available for this file type: {mime_type}")

    return Div()(
        H3(file_name),
        preview_content
    )

def render_file_list(tree: List[Tuple[str, str, str]], current_path: str) -> Div:
    return Table()(
        Tr(
            Th("Name"),
            Th("Size"),
            Th("Kind"),
            Th("Date Added"),
        ),
        *[Tr(
            Td(
                A(item[1], 
                  href=f'/{os.path.relpath(item[2], base_dir)}' if item[0] == 'folder' else '#',
                  hx_get=f'/{os.path.relpath(item[2], base_dir)}?preview=true' if item[0] == 'file' else None,
                  hx_target='#preview-area')
            ),
            Td(format_size(get_file_info(item[2])[0])),
            Td(get_file_info(item[2])[2]),
            Td(format_date(get_file_info(item[2])[1])),
        ) for item in tree]
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

    return Title("File System Interface"), Div(
        # Search form
        Input(
            type="text",
            name="search",
            placeholder="Search files",
            hx_get=f'/{path}',
            hx_trigger="keyup changed delay:500ms",
            hx_push_url="false",
            hx_target="#file-list-container"
        ),
        # Breadcrumb
        Div(*breadcrumb_items),
        # File list and Preview area
        Div(
            # File list
            Div(id="file-list-container")(
                file_list
            ),
            # Preview area
            Div(id='preview-area')(
                P("Select a file to preview")
            )
        )
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
        if preview:
            return render_preview(full_path)
        elif hx_request:
            return file_list
        else:
            return render_main_page(path, file_list)

serve(port=5002)