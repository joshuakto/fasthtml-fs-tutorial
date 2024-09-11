from fasthtml.common import *
import os
import datetime
import mimetypes

app = FastHTML()
rt = app.route

base_dir = os.getcwd()

def build_tree(path: str):
    tree = []
    for item in sorted(os.listdir(path)):
        item_path = os.path.join(path, item)
        relative_path = os.path.relpath(item_path, base_dir)
        if os.path.isdir(item_path):
            tree.append(('folder', item, relative_path))
        else:
            tree.append(('file', item, relative_path))
    return tree

def get_file_info(file_path: str):
    stats = os.stat(file_path)
    return stats.st_size, datetime.datetime.fromtimestamp(stats.st_mtime)

def format_size(size: int):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

def format_date(date: datetime.datetime):
    return date.strftime("%d %b %Y, %I:%M %p")

def handle_directory(path: str):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    tree = build_tree(full_path)
    
    return render_file_list(tree, path)

def render_file_list(tree: List[Tuple[str, str, str]], current_path: str) -> Div:
    return Table()(
        Tr(
            Th("Name"),
            Th("Size"),
            Th("Date Added"),
        ),
        *[Tr(
            Td(
                Span('📁' if item[0] == 'folder' else '📄'), 
                A(item[1], 
                  href=f'/{os.path.relpath(item[2], base_dir)}' if item[0] == 'folder' else '#',
                  hx_get=f'/{os.path.relpath(item[2], base_dir)}?preview=true' if item[0] == 'file' else None,
                  hx_target='#preview-area')
            ),
            Td(format_size(get_file_info(item[2])[0])),
            Td(format_date(get_file_info(item[2])[1])),
        ) for item in tree]
    )
def render_main_page(path: str, file_list: Div):
    breadcrumb_items = [
        A('~', href='/'),
        *[Span('/') +  A(part, href=f'/{"/".join(path.split("/")[:i+1])}')
          for i, part in enumerate(path.split('/')) if part]
    ]

    return Title("File System Interface"), Div(
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

def handle_file(path: str, preview: bool = False):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    mime_type, _ = mimetypes.guess_type(full_path)
    return render_preview(full_path)


@rt("/")
@rt("/{path:path}")
def get(path: str = ''):
    full_path = os.path.normpath(os.path.join(base_dir, path))
    
    if not full_path.startswith(base_dir):
        return Response("Access denied: Path is outside the allowed directory.", status_code=403)
    
    if not os.path.exists(full_path):
        return Response("Path not found", status_code=404)
    
    if os.path.isfile(full_path):
        return handle_file(full_path)
    
    file_list = handle_directory(path)
    return render_main_page(path, file_list)
    

serve(port=5002)