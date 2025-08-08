import os
import tokenize
from io import BytesIO

def is_triple_quoted_string(token_string):
    triple_quotes = ("'''", '"""')
    return (
        (token_string.startswith(triple_quotes) and token_string.endswith(triple_quotes))
        or
        (token_string.startswith("r'''") and token_string.endswith("'''"))
        or
        (token_string.startswith('r"""') and token_string.endswith('"""'))
    )

def remove_comments_and_docstrings(source):
    io_obj = BytesIO(source.encode('utf-8'))
    output_tokens = []
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0

    try:
        tokens = list(tokenize.tokenize(io_obj.readline))
    except tokenize.TokenError:
        return source

    for tok in tokens:
        token_type = tok.type
        token_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        if token_type == tokenize.COMMENT:
            continue

        if token_type == tokenize.STRING:
            if prev_toktype == tokenize.INDENT or last_lineno < start_line - 1:
                if is_triple_quoted_string(token_string):
                    continue

        output_tokens.append(tok)
        prev_toktype = token_type
        last_lineno = end_line
        last_col = end_col

    new_code = tokenize.untokenize(output_tokens).decode('utf-8')
    return new_code

def remove_comments_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        new_source = remove_comments_and_docstrings(source)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_source)

        print(f'Комментарии и докстринги удалены из: {file_path}')
    except Exception as e:
        print(f'Ошибка при обработке файла {file_path}: {e}')

def remove_comments_from_project(root_dir):
    for subdir, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__']]

        for file in files:
            if file.endswith('.py'):
                remove_comments_from_file(os.path.join(subdir, file))

if __name__ == '__main__':
    current_dir = os.getcwd()
    print(f'Обрабатывается текущая папка: {current_dir}')
    remove_comments_from_project(current_dir)