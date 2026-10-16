"""Получить очищенный текст и токены из глав локального EPUB."""
import argparse
import json
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile


def tag(element):
    return element.tag.rsplit('}', 1)[-1]


def blocked(element):
    classes = element.attrib.get('class', '').split()
    style = element.attrib.get('style', '').replace(' ', '').lower()
    epub_type = element.attrib.get('{http://www.idpf.org/2007/ops}type', '').split()
    return (tag(element) in ('script', 'style', 'sup', 'nav')
            or any(c in classes for c in ('ws-noexport', 'references', 'reference', 'noprint', 'footnote'))
            or any(t in epub_type for t in ('noteref', 'footnote', 'endnote'))
            or 'display:none' in style)


def inline_text(element):
    if blocked(element):
        return ''
    parts = [element.text or '']
    for child in element:
        parts.append(inline_text(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def paragraphs(element):
    if blocked(element):
        return []
    if tag(element) == 'p':
        text = re.sub(r'\s+', ' ', inline_text(element)).strip()
        heading = r'(?:[IVXLC]+|ЧАСТЬ\s+\S+|ЭПИЛОГ|Глава\s+[IVXLC]+|Конец)'
        return [] if not text or re.fullmatch(heading, text, re.I) else [text]
    result = []
    for child in element:
        result.extend(paragraphs(child))
    return result


def prepare(source):
    sections, included = [], []
    with ZipFile(source) as archive:
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        opf = next(e.attrib['full-path'] for e in container.iter() if tag(e) == 'rootfile')
        package = ET.fromstring(archive.read(opf))
        manifest = {e.attrib['id']: e.attrib for e in package.iter() if tag(e) == 'item'}
        for ref in package.iter():
            if tag(ref) != 'itemref':
                continue
            item = manifest[ref.attrib['idref']]
            href = unquote(item['href'].split('#')[0])
            # Обе предоставленные книги содержат роман в chapterN / cN_*Glava_*.
            # Исключаем обложку, аннотацию, оглавление и about.xhtml.
            filename = posixpath.basename(href)
            if not (re.fullmatch(r'chapter\d+\.xhtml', filename)
                    or re.fullmatch(r'c\d+_.*Glava_.*\.xhtml', filename)):
                continue
            path = posixpath.normpath(posixpath.join(posixpath.dirname(opf), href))
            document = ET.fromstring(archive.read(path))
            body = next(e for e in document.iter() if tag(e) == 'body')
            content = paragraphs(body)
            if content:
                sections.append('\n\n'.join(content))
                included.append(path)
    if not sections:
        raise ValueError('Главы этого EPUB не распознаны; проверьте структуру книги.')
    text = '\n\n'.join(sections)
    tokens = re.findall(r'[а-яёa-z]+', text.lower())
    if len(tokens) < 100_000:
        raise ValueError(f'Получено меньше 100 тысяч слов: {len(tokens)}')
    source.with_suffix('.txt').write_text(text + '\n', encoding='utf-8')
    clean = source.with_name(source.stem + '_clean.txt')
    token_path = source.with_name(source.stem + '_tokens.txt')
    clean.write_text(text + '\n', encoding='utf-8')
    token_path.write_text(' '.join(tokens) + '\n', encoding='utf-8')
    report = {'source': source.name, 'sections': included, 'words': len(tokens),
              'vocabulary': len(set(tokens)), 'token_pattern': '[а-яёa-z]+',
              'encoding': 'utf-8'}
    source.with_name(source.stem + '_stats.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert token_path.read_text(encoding='utf-8').split() == tokens
    print(f'{source.name}: разделов {len(sections)}, слов {len(tokens):,}, словарь {len(set(tokens)):,}')
    print(f'Начало: {text[:100]}')
    print(f'Конец: {text[-130:]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', type=Path)
    for source in parser.parse_args().sources:
        prepare(source)
