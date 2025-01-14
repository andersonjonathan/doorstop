# SPDX-License-Identifier: LGPL-3.0-only

"""Functions to publish documents and items."""

import os
import shutil
import tempfile
import textwrap
import html

import bottle
import markdown
import yaml
from bottle import template as bottle_template
from plantuml_markdown import PlantUMLMarkdownExtension
from collections import Counter

from doorstop import common, settings
from doorstop.common import DoorstopError
from doorstop.core import Document
from doorstop.core.types import is_item, is_tree, iter_documents, iter_items

EXTENSIONS = (
    'markdown.extensions.extra',
    'markdown.extensions.sane_lists',
    PlantUMLMarkdownExtension(
        server='http://www.plantuml.com/plantuml',
        cachedir=tempfile.gettempdir(),
        format='svg',
        classes='class1,class2',
        title='UML',
        alt='UML Diagram',
    ),
)
CSS = os.path.join(os.path.dirname(__file__), 'files', 'doorstop.css')
PDF_CSS = os.path.join(os.path.dirname(__file__), 'files', 'doorstop_pdf.css')
PDF = 'index.pdf'
HTMLTEMPLATE = 'sidebar'
INDEX = 'index.html'
MATRIX = 'traceability.csv'

log = common.logger(__name__)


def publish(
    obj,
    path,
    ext=None,
    linkify=None,
    index=None,
    matrix=None,
    template=None,
    toc=True,
    **kwargs,
):
    """Publish an object to a given format.

    The function can be called in two ways:

    1. document or item-like object + output file path
    2. tree-like object + output directory path

    :param obj: (1) Item, list of Items, Document or (2) Tree
    :param path: (1) output file path or (2) output directory path
    :param ext: file extension to override output extension
    :param linkify: turn links into hyperlinks (for Markdown or HTML)
    :param index: create an index.html (for HTML)
    :param matrix: create a traceability matrix, traceability.csv

    :raises: :class:`doorstop.common.DoorstopError` for unknown file formats

    :return: output location if files created, else None

    """
    # Determine the output format
    ext = ext or os.path.splitext(path)[-1] or '.html'
    check(ext)
    if linkify is None:
        linkify = is_tree(obj) and ext in ['.html', '.md', '.pdf']
    if index is None:
        index = is_tree(obj) and ext == '.html'
    if matrix is None:
        matrix = is_tree(obj)

    if is_tree(obj):
        assets_dir = os.path.join(path, Document.ASSETS)  # path is a directory name
    else:
        assets_dir = os.path.join(
            os.path.dirname(path), Document.ASSETS
        )  # path is a filename

    if os.path.isdir(assets_dir):
        log.info('Deleting contents of assets directory %s', assets_dir)
        common.delete_contents(assets_dir)
    else:
        os.makedirs(assets_dir)

    # If publish html and then markdown ensure that the html template are still available
    if not template:
        template = HTMLTEMPLATE
    template_assets = os.path.join(os.path.dirname(__file__), 'files', 'assets')
    if os.path.isdir(template_assets):
        log.info("Copying %s to %s", template_assets, assets_dir)
        common.copy_dir_contents(template_assets, assets_dir)

    count = 0
    # Publish documents
    if ext == '.pdf':
        linkify = False
        all_lines = []
        toc = '### Table of Contents\n\n'

        for document in sorted(obj.documents):
            if document.prefix == 'TEST':
                continue
            count += 1
            for item in iter_items(document):
                if item.depth == 1:
                    prefix = ' * '
                else:
                    continue

                if item.heading:
                    lines = item.text.splitlines()
                    heading = lines[0] if lines else ''
                elif item.header:
                    heading = "{h}".format(h=item.header)
                else:
                    heading = item.uid

                if settings.PUBLISH_HEADING_LEVELS:
                    level = _format_level(item.level)
                    level = f"{count}{level[1:]}"
                    if level.endswith('.0'):
                        level = level[:-2]
                    lbl = '{lev} {h}'.format(lev=level, h=heading)
                else:
                    lbl = heading

                line = '{p}{lbl}\n'.format(p=prefix, lbl=lbl)
                toc += line

            lines = publish_lines(
                document, ext, linkify=linkify, template=template, toc=toc, count=count, **kwargs
            )

            all_lines += lines
            all_lines += ['<div style="clear: both; page-break-after: always;"> </div>']
            if document.copy_assets(assets_dir):
                log.info('Copied assets from %s to %s', obj.assets, assets_dir)
        shutil.copyfile(PDF_CSS, os.path.join(assets_dir, 'doorstop_pdf.css'))
        all_lines = [
                        f'<H1 style="text-align: center;">{settings.TITLE}</H1>',
                        f'<H3 style="text-align: center;">{settings.VERSION}</H3>',
                        '<div style="clear: both; page-break-after: always;"> </div>',
                        toc,
                        '<div style="clear: both; page-break-after: always;"> </div>'
                    ] + all_lines
        path2 = os.path.join(path, 'index.md')
        common.write_lines(all_lines, path2)
        from md2pdf.core import md2pdf
        path2 = os.path.join(path, PDF)
        md2pdf(path2,
               md_content='\n'.join(all_lines),
               md_file_path=None,
               css_file_path=os.path.join(assets_dir, 'doorstop_pdf.css'),
               base_url=path)
    else:
        for obj2, path2 in iter_documents(obj, path, ext):
            count += 1

            # Publish content to the specified path
            log.info("publishing to {}...".format(path2))
            lines = publish_lines(
                obj2, ext, linkify=linkify, template=template, toc=toc, **kwargs
            )
            common.write_lines(lines, path2)
            if obj2.copy_assets(assets_dir):
                log.info('Copied assets from %s to %s', obj.assets, assets_dir)

    # Create index
    if index and count:
        _index(path, tree=obj if is_tree(obj) else None)

    # Create traceability matrix
    if index and matrix and count:
        _matrix(path, tree=obj if is_tree(obj) else None)

    # Return the published path
    if count:
        msg = "published to {} file{}".format(count, 's' if count > 1 else '')
        log.info(msg)
        return path
    else:
        log.warning("nothing to publish")
        return None


def _index(directory, index=INDEX, extensions=('.html',), tree=None):
    """Create an HTML index of all files in a directory.

    :param directory: directory for index
    :param index: filename for index
    :param extensions: file extensions to include
    :param tree: optional tree to determine index structure

    """
    # Get paths for the index index
    filenames = []
    for filename in os.listdir(directory):
        if filename.endswith(extensions) and filename != INDEX:
            filenames.append(os.path.join(filename))

    # Create the index
    if filenames:
        path = os.path.join(directory, index)
        log.info("creating an {}...".format(index))
        lines = _lines_index(sorted(filenames), tree=tree, link_to_pdf=os.path.exists(os.path.join(directory, PDF)))
        common.write_lines(lines, path)
    else:
        log.warning("no files for {}".format(index))


def _lines_index(filenames, charset='UTF-8', tree=None, link_to_pdf=False):
    """Yield lines of HTML for index.html.

    :param filesnames: list of filenames to add to the index
    :param charset: character encoding for output
    :param tree: optional tree to determine index structure

    """
    yield '<!DOCTYPE html>'
    yield '<head>'
    yield (
        '<meta http-equiv="content-type" content="text/html; '
        'charset={charset}">'.format(charset=charset)
    )
    baseurl = bottle.SimpleTemplate.defaults['baseurl'] or ''
    yield f'<link rel="stylesheet" href="{baseurl}assets/doorstop/bootstrap.min.css" />'
    yield f'<link rel="stylesheet" href="{baseurl}assets/doorstop/general.css" />'
    yield '<style type="text/css">'
    yield from _lines_css()
    yield '</style>'
    yield '<title>'
    yield f'{settings.TITLE} - {settings.VERSION}'
    yield '</title>'
    yield '</head>'
    yield '<body>'
    yield '<h1>'
    yield f'{settings.TITLE} - {settings.VERSION}'
    yield '</h1>'

    # Additional files
    if filenames:
        documents = tree.documents if tree else None
        yield ''
        yield '<h3>Published Documents:</h3>'
        yield '<p>'
        yield '<ul>'
        for document in sorted(documents):
            yield '<li><a href="{p}.html">{n} ({p})</a></li>'.format(p=document.prefix, n=document.name)
        yield '</ul>'
        yield '</p>'
        yield ''
        yield '<hr>'
        yield ''
        if link_to_pdf:
            yield f'<br/><a href="./{PDF}">Requirements as PDF</a><br/><br/>'
            yield ''
            yield ''
            yield '<hr/>'
            yield ''
        yield '<h3>Search:</h3>'
        yield '<input type="text" name="search" id="search-field"/>'
        yield '<pre id="search-result">'
        yield '</pre>'

        yield '<script>'
        yield 'const data = ['

        for document in sorted(documents):
            for item in document.items:
                text = item.text.lower().replace('\n', '\\n').replace("'", "\\'")
                yield '{{link: \'<a href="{p}.html#{i}" title="{title_content}">{n} ({p}) - {i_n}</a>\', text: \'{content}\'}},'.format(
                    p=document.prefix,
                    n=document.name,
                    i=item.uid,
                    i_n=str(item),
                    title_content=f"{item.uid} {str(item.stakeholder_item) if item.stakeholder else ''} {text}".replace(
                        '"', '&quot;'),
                    content=f"{item.uid} {str(item.stakeholder_item) if item.stakeholder else ''} {text}")
        yield '];'

        yield 'const searchField = document.getElementById("search-field");'
        yield 'const searchResult = document.getElementById("search-result");'
        yield 'const search = () => {'
        yield 'const value = searchField.value.toLowerCase().split(" ");'
        yield 'const res = data.filter(obj => value.every((v) => obj.text.includes(v)));'
        yield 'searchResult.innerHTML = res.map(obj => obj.link).join("\\n");'
        yield '};'
        yield 'searchField.addEventListener("input", search);'
        yield '</script>'

    if tree:
        yield ''
        yield '<hr>'
        yield ''
        yield '<h3>Traceability matrix:</h3>'
        test_cases = {}
        requirements = {}
        use_cases = {
            None: []
        }
        documents = tree.documents if tree else None
        if documents:
            result = {}
            if os.path.isfile(settings.RESULT_FILE):
                with open(settings.RESULT_FILE, 'r') as in_file:
                    result = yaml.load(in_file, Loader=yaml.FullLoader)  # noqa: S506
            all_tests = set()
            linked_tests = set()
            badge_mapping = {
                'passed': '<span class="label label-success" title="{count} Passed">✓  {count}</span>',
                'error': '<span class="label label-danger" title="{count} Error">!  {count}</span>',
                'failure': '<span class="label label-danger" title="{count} Failed">✗  {count}</span>',
                'skipped': '<span class="label label-default" title="{count} skipped">-  {count}</span>',
            }
            for document in sorted(documents):
                for item in document.items:
                    if str(item).startswith('TEST'):
                        all_tests.add(item)
                    if (str(item).startswith('USECASE') or str(item).startswith('RISK')) and item not in use_cases:
                        use_cases[item] = []
                    if not (
                        str(item).startswith('TEST') or
                        str(item).startswith('ROLE') or
                        str(item).startswith('USECASE') or
                        str(item).startswith('RISK') or
                        str(item).startswith('HEAD')
                    ):
                        no_use_case = True
                        for use_case in item.parent_items:
                            if str(use_case).startswith('USECASE') or str(use_case).startswith('RISK'):
                                no_use_case = False
                                if use_case in use_cases:
                                    use_cases[use_case].append(item)
                                else:
                                    use_cases[use_case] = [item]
                        if no_use_case:
                            use_cases[None].append(item)
                        test_links = []
                        for l in item.find_child_items(skip_parent_check=True):
                            if str(l).startswith('TEST'):
                                linked_tests.add(l)
                                if str(l.uid) in result:
                                    d = result[str(l.uid)]
                                    test_cases[l] = [
                                        badge_mapping[x[0]].format(count=x[1])
                                        for x in sorted(
                                            Counter([x['status'] for x in d]).items(),
                                            key=lambda x: x[0]
                                        )
                                    ]
                                else:
                                    test_cases[l] = []
                                test_links.append(l)
                        requirements[item] = test_links
            test_links = []
            for l in all_tests.difference(linked_tests):
                linked_tests.add(l)
                if str(l.uid) in result:
                    d = result[str(l.uid)]
                    test_cases[l] = [
                        badge_mapping[x[0]].format(count=x[1])
                        for x in sorted(
                            Counter([x['status'] for x in d]).items(),
                            key=lambda x: x[0]
                        )
                    ]
                else:
                    test_cases[l] = []
                test_links.append(l)
            requirements[None] = test_links
            use_cases[None].append(None)

            rows = []
            for use_case, use_case_requirements in sorted(use_cases.items(),
                                                          key=lambda x: (x[0] is None, str(x[0].uid) if x[0] else '')):
                for requirement in sorted(use_case_requirements, key=lambda x: (x is None, str(x.uid) if x else '')):
                    for test_case in sorted(requirements[requirement],
                                            key=lambda x: (x is None, str(x.uid) if x else '')):
                        rows.append((use_case, requirement, test_case, test_cases[test_case]))
                    if len(requirements[requirement]) == 0:
                        rows.append((use_case, requirement, None, None))
                if len(use_case_requirements) == 0:
                    rows.append((use_case, None, None, None))

            # yield '<table class="table table-condensed table-bordered table-striped">'
            yield '<table class="table table-condensed">'
            yield '<thead>'
            yield '<tr>'
            yield '<th>Use case / Risk</th>'
            yield '<th>Requirements</th>'
            yield '<th>Test cases</th>'
            yield '<th>Test result</th>'
            yield '</tr>'
            yield '</thead>'
            yield '<tbody>'
            prev_use_case = ""
            prev_requirement = None
            for idx, (use_case, requirement, test_case, result) in enumerate(rows):
                yield '<tr>'
                if use_case != prev_use_case:
                    i = 0
                    for uc, _, _, _ in rows[idx:]:
                        if uc != use_case:
                            break
                        i += 1
                    yield f'<td rowspan="{i}">{create_link(use_case) if use_case else "No use case"}</td>'
                if requirement != prev_requirement or use_case != prev_use_case:
                    i = 0
                    for uc, r, _, _ in rows[idx:]:
                        if r != requirement or uc != use_case:
                            break
                        i += 1
                    im = ''
                    if (requirement
                        and 'implemented' in requirement.data
                        and requirement.data.get('implemented') not in [None, '']
                    ):
                        implemented = str(requirement.data.get('implemented')).strip() not in [
                            None, False, '', 'false', 'False', "''", '""', '0']
                        im = (
                            '<small><span class="label {css_class}" title="{title}">{implemented}</span></small>'
                        ).format(
                            css_class="label-success" if implemented else 'label-danger',
                            title="Implemented" if implemented else 'Not implemented',
                            implemented='✓' if implemented else '✗'
                        )
                    yield f'<td rowspan="{i}">'
                    yield f'{create_link(requirement) if requirement else "No requirement"}&nbsp;&nbsp;{im}'
                    yield '</td>'
                yield f'<td>{create_link(test_case) if test_case else "No test case"}</td>'
                yield f'<td>{" ".join(result) if result else ""}</td>'
                yield '</tr>'
                prev_use_case = use_case
                prev_requirement = requirement
            yield '</tbody>'
            yield '</table>'

        # Tree structure
    text = tree.draw() if tree else None
    if text:
        if filenames:
            yield ''
            yield '<hr>'
        yield ''
        yield '<h3>Tree Structure:</h3>'
        yield '<pre><code>' + text + '</pre></code>'

    yield '</body>'
    yield '</html>'


def create_link(item):
    """Create a link."""
    return '<a title="{t}" href="{p}.html#{i}">{i_n}</a>'.format(
        p=item.document.prefix if hasattr(item, 'document') and hasattr(item.document, 'prefix') else '',
        i=item.uid if hasattr(item, 'uid') else '',
        t=html.escape(item.text if hasattr(item, 'text') else ''),
        i_n=str(item)
    )


def _lines_css():
    """Yield lines of CSS to embedded in HTML."""
    yield ''
    for line in common.read_lines(CSS):
        yield line.rstrip()
    yield ''


def _matrix(directory, tree, filename=MATRIX, ext=None):
    """Create a traceability matrix for all the items.

    :param directory: directory for matrix
    :param tree: tree to access the traceability data
    :param filename: filename for matrix
    :param ext: file extensionto use for the matrix

    """
    # Get path and format extension
    path = os.path.join(directory, filename)
    ext = ext or os.path.splitext(path)[-1] or '.csv'

    # Create the matrix
    if tree:
        log.info("creating an {}...".format(filename))
        content = _matrix_content(tree)
        common.write_csv(content, path)
    else:
        log.warning("no data for {}".format(filename))


def _extract_prefix(document):
    if document:
        return document.prefix
    else:
        return None


def _extract_uid(item):
    if item:
        return item.uid
    else:
        return None


def _matrix_content(tree):
    """Yield rows of content for the traceability matrix."""
    yield tuple(map(_extract_prefix, tree.documents))
    for row in tree.get_traceability():
        yield tuple(map(_extract_uid, row))


def publish_lines(obj, ext='.txt', **kwargs):
    """Yield lines for a report in the specified format.

    :param obj: Item, list of Items, or Document to publish
    :param ext: file extension to specify the output format

    :raises: :class:`doorstop.common.DoorstopError` for unknown file formats

    """
    gen = check(ext)
    log.debug("yielding {} as lines of {}...".format(obj, ext))
    yield from gen(obj, **kwargs)


def _lines_text(obj, indent=8, width=79, **_):
    """Yield lines for a text report.

    :param obj: Item, list of Items, or Document to publish
    :param indent: number of spaces to indent text
    :param width: maximum line length

    :return: iterator of lines of text

    """
    for item in iter_items(obj):

        level = _format_level(item.level)

        if item.heading:

            # Level and Text
            if settings.PUBLISH_HEADING_LEVELS:
                yield "{lev:<{s}}{t}".format(lev=level, s=indent, t=item.text)
            else:
                yield "{t}".format(t=item.text)

        else:

            # Level and UID
            if item.header:
                yield "{lev:<{s}}{u} {header}".format(
                    lev=level, s=indent, u=item.uid, header=item.header
                )
            else:
                yield "{lev:<{s}}{u}".format(lev=level, s=indent, u=item.uid)

            # Text
            if item.text:
                yield ""  # break before text
                for line in item.text.splitlines():
                    yield from _chunks(line, width, indent)

                    if not line:
                        yield ""  # break between paragraphs

            # Reference
            if item.ref:
                yield ""  # break before reference
                ref = _format_text_ref(item)
                yield from _chunks(ref, width, indent)

            # References
            if item.references:
                yield ""  # break before references
                ref = _format_text_references(item)
                yield from _chunks(ref, width, indent)

            # stakeholder
            if item.stakeholder:
                yield ""  # break before references
                yield from _chunks(f"Stakeholder: {str(item.stakeholder_item)}", width, indent)

            # Prio
            if 'prio' in item.data and item.data.get('prio'):
                yield ""  # break before references
                yield from _chunks(f"Priority: {str(item.data.get('prio')).strip()}", width, indent)

            # Implemented
            if 'implemented' in item.data and item.data.get('implemented'):
                yield ""  # break before references
                yield from _chunks(f"Implemented: {str(item.data.get('implemented')).strip()}", width, indent)

            # Jira links
            if 'jira' in item.data and item.data.get('jira'):
                yield ""  # break before links
                jira_items = item.data.get('jira')
                label = "Jira issues: "
                links = ', '.join(jira_items)
                slinks = label + links
                yield from _chunks(slinks, width, indent)

            # Links
            if item.links:
                yield ""  # break before links
                if settings.PUBLISH_CHILD_LINKS:
                    label = "Requirements:" if str(item).startswith('TEST') else "Parent links:"
                else:
                    label = "Links: "
                slinks = label + ', '.join(str(l) for l in item.links)
                yield from _chunks(slinks, width, indent)
            if settings.PUBLISH_CHILD_LINKS:
                links = item.find_child_links(skip_parent_check=True)
                if links:
                    child_links = [str(l) for l in links if not str(l).startswith('TEST')]
                    test_links = [str(l) for l in links if str(l).startswith('TEST')]
                    if child_links:
                        yield ""  # break before links
                        slinks = "Child links: " + ', '.join(child_links)
                        yield from _chunks(slinks, width, indent)
                    if test_links:
                        yield ""  # break before links
                        slinks = "Tests: " + ', '.join(test_links)
                        yield from _chunks(slinks, width, indent)
                stakeholder_links = item.find_stakeholder_items()
                if stakeholder_links:
                    child_links = [str(l) for l in stakeholder_links]
                    if child_links:
                        yield ""  # break before links
                        slinks = "Linked to stakeholder: " + ', '.join(child_links)
                        yield from _chunks(slinks, width, indent)

            if item.document and item.document.publish:
                yield ""
                for attr in item.document.publish:
                    if not item.attribute(attr):
                        continue
                    attr_line = "{}: {}".format(attr, item.attribute(attr))
                    yield from _chunks(attr_line, width, indent)

        yield ""  # break between items


def _chunks(text, width, indent):
    """Yield wrapped lines of text."""
    yield from textwrap.wrap(
        text, width, initial_indent=' ' * indent, subsequent_indent=' ' * indent
    )


def _lines_markdown(obj, **kwargs):
    """Yield lines for a Markdown report.

    :param obj: Item, list of Items, or Document to publish
    :param linkify: turn links into hyperlinks (for conversion to HTML)

    :return: iterator of lines of text

    """
    linkify = kwargs.get('linkify', False)
    for item in iter_items(obj):

        heading = '#' * item.depth
        level = _format_level(item.level)

        if item.heading:
            text_lines = item.text.splitlines()
            # Level and Text
            if settings.PUBLISH_HEADING_LEVELS:
                standard = "{h} {lev} {t}".format(
                    h=heading, lev=level, t=text_lines[0] if text_lines else ''
                )
            else:
                standard = "{h} {t}".format(
                    h=heading, t=text_lines[0] if text_lines else ''
                )
            attr_list = _format_md_attr_list(item, True)
            yield standard + attr_list
            yield from text_lines[1:]
        else:

            uid = item.uid
            if settings.ENABLE_HEADERS:
                # Implemented
                if item.header:
                    if str(item.uid).startswith('HEAD'):
                        uid = '{h}'.format(h=item.header)
                    else:
                        uid = '{h} <small>{u}</small>'.format(h=item.header, u=item.uid)
                else:
                    uid = '{u}'.format(u=item.uid)
                if 'implemented' in item.data and item.data.get('implemented') not in [None, '']:
                    implemented = str(item.data.get('implemented')).strip() not in [None, False, '', 'false', 'False',
                                                                                    "''", '""', '0']
                    uid = '{uid} <small><span class="label {css_class}" title="{title}">{implemented}</span></small>'.format(
                        uid=uid,
                        css_class="label-success" if implemented else 'label-danger',
                        title="Implemented" if implemented else 'Not implemented',
                        implemented='✓' if implemented else '✗'
                    )

            # Level and UID
            if settings.PUBLISH_BODY_LEVELS:
                standard = "{h} {lev} {u}".format(h=heading, lev=level, u=uid)
            else:
                standard = "{h} {u}".format(h=heading, u=uid)

            attr_list = _format_md_attr_list(item, True)
            yield standard + attr_list

            if 'risk-rating' in item.data and item.data.get('risk-rating'):
                risk_rating = item.data.get('risk-rating', {})
                detectability = risk_rating.get('detectability', None)
                probability = risk_rating.get('probability', None)
                severity = risk_rating.get('severity', None)
                rpn = '-'
                if detectability is not None and probability is not None and severity is not None:
                    rpn = int(detectability) * int(probability) * int(severity)
                detectability = detectability if detectability is not None else '-'
                probability = probability if probability is not None else '-'
                severity = severity if severity is not None else '-'
                yield ""  # break before references
                yield "&nbsp; | Detectability | Probability | Severity | Risk Priority Number"
                yield "------ | ------------- | ----------- | -------- | --------------------"
                yield f"__Before mitigation__ | {detectability} | {probability} | {probability} | __{rpn}__"

                if 'residual-risk-rating' in item.data and item.data.get('residual-risk-rating'):
                    risk_rating = item.data.get('residual-risk-rating', {})
                    detectability = risk_rating.get('detectability', None)
                    probability = risk_rating.get('probability', None)
                    severity = risk_rating.get('severity', None)
                    rpn = '-'
                    if detectability is not None and probability is not None and severity is not None:
                        rpn = int(detectability) * int(probability) * int(severity)
                    detectability = detectability if detectability is not None else '-'
                    probability = probability if probability is not None else '-'
                    severity = severity if severity is not None else '-'
                    yield f"__After mitigation__ | {detectability} | {probability} | {probability} | __{rpn}__"
                    yield ""  # break before references

            # Text
            if item.text:
                yield ""  # break before text
                yield from item.text.splitlines()

            # Reference
            if item.ref:
                yield ""  # break before reference
                yield _format_md_ref(item)

            # Reference
            if item.references:
                yield ""  # break before reference
                yield _format_md_references(item)

            # stakeholder
            if item.stakeholder:
                yield ""  # break before references
                links = _format_md_links([item.stakeholder_item], linkify)
                yield _format_md_label_links("Stakeholder:", links, linkify)

            # Prio
            if 'prio' in item.data and item.data.get('prio'):
                yield ""  # break before references
                yield f"Priority: {str(item.data.get('prio')).strip()}"

            # Jira links
            if 'jira' in item.data and item.data.get('jira'):
                yield ""  # break before links
                jira_items = item.data.get('jira')
                label = "Jira issues:"
                links = ', '.join(["[{jira_issue}]({base_url}/browse/{jira_issue})".format(
                    jira_issue=jira_item,
                    base_url=settings.JIRA_URL
                ) for jira_item in jira_items])
                label_links = _format_md_label_links(label, links, linkify)
                yield label_links

            # Parent links
            if item.links:
                yield ""  # break before links
                items2 = sorted(item.parent_items, key=lambda x: x.uid)
                parent_links = [l for l in items2 if not (
                    str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                test_links = [l for l in items2 if str(l).startswith('TEST')]
                risk_links = [l for l in items2 if str(l).startswith('RISK')]
                if use_case_links:
                    yield ""  # break before links
                    label = "Use cases:"
                    links = _format_md_links(use_case_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if parent_links:
                    yield ""  # break before links
                    label = "Parent links:"
                    links = _format_md_links(parent_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if test_links:
                    yield ""  # break before links
                    label = "Tests:"
                    links = _format_md_links(test_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if risk_links:
                    yield ""  # break before links
                    label = "Risks:"
                    links = _format_md_links(risk_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links

            # Child links
            if settings.PUBLISH_CHILD_LINKS:
                items2 = sorted(item.find_child_items(skip_parent_check=True), key=lambda x: x.uid)
                if items2:
                    parent_links = [l for l in items2 if not (
                        str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                    use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                    test_links = [l for l in items2 if str(l).startswith('TEST')]
                    risk_links = [l for l in items2 if str(l).startswith('RISK')]
                    if use_case_links:
                        yield ""  # break before links
                        label = "Use cases:"
                        links = _format_md_links(use_case_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if parent_links:
                        yield ""  # break before links
                        label = "Child links:"
                        if str(item).startswith('USECASE'):
                            label = "Requirements:"
                        if str(item).startswith('RISK'):
                            label = "Requirements for mitigating the risk:"
                        links = _format_md_links(parent_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if test_links:
                        yield ""  # break before links
                        label = "Tests:"
                        links = _format_md_links(test_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if risk_links:
                        yield ""  # break before links
                        label = "Risks:"
                        links = _format_md_links(risk_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links

                stakeholder_links = item.find_stakeholder_items()
                if stakeholder_links:
                    items2 = sorted(stakeholder_links, key=lambda x: x.uid)
                    parent_links = [l for l in items2 if not (
                            str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                    use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                    test_links = [l for l in items2 if str(l).startswith('TEST')]
                    risk_links = [l for l in items2 if str(l).startswith('RISK')]
                    if use_case_links:
                        yield ""  # break before links
                        label = "Use cases linked to stakeholder:"
                        links = _format_md_links(use_case_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if parent_links:
                        yield ""  # break before links
                        label = "Requirements linked to stakeholder:"
                        links = _format_md_links(parent_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if test_links:
                        yield ""  # break before links
                        label = "Tests linked to stakeholder:"
                        links = _format_md_links(test_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if risk_links:
                        yield ""  # break before links
                        label = "Risks linked to stakeholder:"
                        links = _format_md_links(risk_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links

            # Add custom publish attributes
            if item.document and item.document.publish:
                header_printed = False
                for attr in item.document.publish:
                    if not item.attribute(attr):
                        continue
                    if not header_printed:
                        header_printed = True
                        yield ""
                        yield "| Attribute | Value |"
                        yield "| --------- | ----- |"
                    yield "| {} | {} |".format(attr, item.attribute(attr))
                yield ""

        yield ""  # break between items


def _lines_markdown_pdf(obj, count, **kwargs):
    """Yield lines for a Markdown report.

    :param obj: Item, list of Items, or Document to publish
    :param linkify: turn links into hyperlinks (for conversion to HTML)

    :return: iterator of lines of text

    """
    linkify = kwargs.get('linkify', False)
    for item in iter_items(obj):

        heading = '#' * item.depth
        level = _format_level(item.level)
        level = f"{count}{level[1:]}"
        if level.endswith('.0'):
            level = level[:-2]
        if item.heading:
            text_lines = item.text.splitlines()
            # Level and Text
            if settings.PUBLISH_HEADING_LEVELS:
                standard = "{h} {lev} {t}".format(
                    h=heading, lev=level, t=text_lines[0] if text_lines else ''
                )
            else:
                standard = "{h} {t}".format(
                    h=heading, t=text_lines[0] if text_lines else ''
                )
            attr_list = ''
            if linkify:
                attr_list = _format_md_attr_list(item, True)
            yield standard + attr_list
            yield from text_lines[1:]
        else:

            uid = item.uid
            if settings.ENABLE_HEADERS:
                # Implemented
                if item.header:
                    if str(item.uid).startswith('HEAD'):
                        uid = '{h}'.format(h=item.header)
                    else:
                        uid = '{h} <small>{u}</small>'.format(h=item.header, u=item.uid)
                else:
                    uid = '{u}'.format(u=item.uid)
                if 'implemented' in item.data and item.data.get('implemented') not in [None, '']:
                    implemented = str(item.data.get('implemented')).strip() not in [None, False, '', 'false', 'False',
                                                                                    "''", '""', '0']
                    uid = '{uid} <small><span class="label {css_class}" title="{title}">{implemented}</span></small>'.format(
                        uid=uid,
                        css_class="label-success" if implemented else 'label-danger',
                        title="Implemented" if implemented else 'Not implemented',
                        implemented='✓' if implemented else '✗'
                    )
                # Prio
                if 'prio' in item.data and item.data.get('prio'):
                    uid = f"{uid} <small>({str(item.data.get('prio')).strip()})</small>"

            # Level and UID
            if settings.PUBLISH_BODY_LEVELS:
                standard = "{h} {lev} {u}".format(h=heading, lev=level, u=uid)
            else:
                standard = "{h} {u}".format(h=heading, u=uid)
            attr_list = ''
            if linkify:
                attr_list = _format_md_attr_list(item, True)
            yield standard + attr_list

            if 'risk-rating' in item.data and item.data.get('risk-rating'):
                risk_rating = item.data.get('risk-rating', {})
                detectability = risk_rating.get('detectability', None)
                probability = risk_rating.get('probability', None)
                severity = risk_rating.get('severity', None)
                rpn = '-'
                if detectability is not None and probability is not None and severity is not None:
                    rpn = int(detectability) * int(probability) * int(severity)
                detectability = detectability if detectability is not None else '-'
                probability = probability if probability is not None else '-'
                severity = severity if severity is not None else '-'
                yield ""  # break before references
                yield "&nbsp; | Detectability | Probability | Severity | Risk Priority Number"
                yield "------ | ------------- | ----------- | -------- | --------------------"
                yield f"__Before mitigation__ | {detectability} | {probability} | {probability} | __{rpn}__"

                if 'residual-risk-rating' in item.data and item.data.get('residual-risk-rating'):
                    risk_rating = item.data.get('residual-risk-rating', {})
                    detectability = risk_rating.get('detectability', None)
                    probability = risk_rating.get('probability', None)
                    severity = risk_rating.get('severity', None)
                    rpn = '-'
                    if detectability is not None and probability is not None and severity is not None:
                        rpn = int(detectability) * int(probability) * int(severity)
                    detectability = detectability if detectability is not None else '-'
                    probability = probability if probability is not None else '-'
                    severity = severity if severity is not None else '-'
                    yield f"__After mitigation__ | {detectability} | {probability} | {probability} | __{rpn}__"
                    yield ""  # break before references

            # Text
            if item.text:
                yield ""  # break before text
                yield from item.text.splitlines()

            # Reference
            if item.ref:
                yield ""  # break before reference
                yield _format_md_ref(item)

            # Reference
            if item.references:
                yield ""  # break before reference
                yield _format_md_references(item)

            # stakeholder
            if item.stakeholder:
                yield ""  # break before references
                links = _format_md_links([item.stakeholder_item], linkify)
                yield _format_md_label_links("Stakeholder:", links, linkify)

            # Jira links
            if 'jira' in item.data and item.data.get('jira'):
                yield ""  # break before links
                jira_items = item.data.get('jira')
                label = "Jira issues:"
                links = ', '.join(["[{jira_issue}]({base_url}/browse/{jira_issue})".format(
                    jira_issue=jira_item,
                    base_url=settings.JIRA_URL
                ) for jira_item in jira_items])
                label_links = _format_md_label_links(label, links, linkify)
                yield label_links

            # Parent links
            if item.links:
                yield ""  # break before links
                items2 = sorted(item.parent_items, key=lambda x: x.uid)
                parent_links = [l for l in items2 if not (
                    str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                test_links = [l for l in items2 if str(l).startswith('TEST')]
                risk_links = [l for l in items2 if str(l).startswith('RISK')]
                if use_case_links:
                    yield ""  # break before links
                    label = "Use cases:"
                    links = _format_md_links(use_case_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if parent_links:
                    yield ""  # break before links
                    label = "Parent links:"
                    links = _format_md_links(parent_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if test_links:
                    yield ""  # break before links
                    label = "Tests:"
                    links = _format_md_links(test_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links
                if risk_links:
                    yield ""  # break before links
                    label = "Risks:"
                    links = _format_md_links(risk_links, linkify)
                    label_links = _format_md_label_links(label, links, linkify)
                    yield label_links

            # Child links
            if settings.PUBLISH_CHILD_LINKS:
                items2 = sorted(item.find_child_items(skip_parent_check=True), key=lambda x: x.uid)
                if items2:
                    parent_links = [l for l in items2 if not (
                        str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                    use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                    test_links = [l for l in items2 if str(l).startswith('TEST')]
                    risk_links = [l for l in items2 if str(l).startswith('RISK')]
                    if use_case_links:
                        yield ""  # break before links
                        label = "Use cases:"
                        links = _format_md_links(use_case_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if parent_links:
                        yield ""  # break before links
                        label = "Child links:"
                        if str(item).startswith('USECASE'):
                            label = "Requirements:"
                        if str(item).startswith('RISK'):
                            label = "Requirements for mitigating the risk:"
                        links = _format_md_links(parent_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if test_links:
                        yield ""  # break before links
                        label = "Tests:"
                        links = _format_md_links(test_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if risk_links:
                        yield ""  # break before links
                        label = "Risks:"
                        links = _format_md_links(risk_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links

                stakeholder_links = item.find_stakeholder_items()
                if stakeholder_links:
                    items2 = sorted(stakeholder_links, key=lambda x: x.uid)
                    parent_links = [l for l in items2 if not (
                            str(l).startswith('TEST') or str(l).startswith('USECASE') or str(l).startswith('RISK'))]
                    use_case_links = [l for l in items2 if str(l).startswith('USECASE')]
                    test_links = [l for l in items2 if str(l).startswith('TEST')]
                    risk_links = [l for l in items2 if str(l).startswith('RISK')]
                    if use_case_links:
                        yield ""  # break before links
                        label = "Use cases linked to stakeholder:"
                        links = _format_md_links(use_case_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if parent_links:
                        yield ""  # break before links
                        label = "Requirements linked to stakeholder:"
                        links = _format_md_links(parent_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if test_links:
                        yield ""  # break before links
                        label = "Tests linked to stakeholder:"
                        links = _format_md_links(test_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links
                    if risk_links:
                        yield ""  # break before links
                        label = "Risks linked to stakeholder:"
                        links = _format_md_links(risk_links, linkify)
                        label_links = _format_md_label_links(label, links, linkify)
                        yield label_links

            # Add custom publish attributes
            if item.document and item.document.publish:
                header_printed = False
                for attr in item.document.publish:
                    if not item.attribute(attr):
                        continue
                    if not header_printed:
                        header_printed = True
                        yield ""
                        yield "| Attribute | Value |"
                        yield "| --------- | ----- |"
                    yield "| {} | {} |".format(attr, item.attribute(attr))
                yield ""

        yield ""  # break between items


def _format_level(level):
    """Convert a level to a string and keep zeros if not a top level."""
    text = str(level)
    if text.endswith('.0') and len(text) > 3:
        text = text[:-2]
    return text


def _format_md_attr_list(item, linkify):
    """Create a Markdown attribute list for a heading."""
    return " {{#{u} }}".format(u=item.uid) if linkify else ''


def _format_text_ref(item):
    """Format an external reference in text."""
    if settings.CHECK_REF:
        path, line = item.find_ref()
        path = path.replace('\\', '/')  # always use unix-style paths
        if line:
            return "Reference: {p} (line {line})".format(p=path, line=line)
        else:
            return "Reference: {p}".format(p=path)
    else:
        return "Reference: '{r}'".format(r=item.ref)


def _format_text_references(item):
    """Format an external reference in text."""
    if settings.CHECK_REF:
        ref = item.find_references()
        text_refs = []
        for ref_item in ref:
            path, line = ref_item
            path = path.replace('\\', '/')  # always use unix-style paths
            if line:
                text_refs.append("{p} (line {line})".format(p=path, line=line))
            else:
                text_refs.append("{p}".format(p=path))
        return "Reference: {}".format(', '.join(ref for ref in text_refs))
    else:
        references = item.references
        text_refs = []
        for ref_item in references:
            path = ref_item['path']
            path = path.replace('\\', '/')  # always use unix-style paths
            text_refs.append("'{p}'".format(p=path))
        return "Reference: {}".format(', '.join(text_ref for text_ref in text_refs))


def _format_md_ref(item):
    """Format an external reference in Markdown."""
    if settings.CHECK_REF:
        path, line = item.find_ref()
        path = path.replace('\\', '/')  # always use unix-style paths
        if line:
            return "> `{p}` (line {line})".format(p=path, line=line)
        else:
            return "> `{p}`".format(p=path)
    else:
        return "> '{r}'".format(r=item.ref)


def _format_md_references(item):
    """Format an external reference in Markdown."""
    if settings.CHECK_REF:
        references = item.find_references()
        text_refs = []
        for ref_item in references:
            path, line = ref_item
            path = path.replace('\\', '/')  # always use unix-style paths

            if line:
                text_refs.append("> `{p}` (line {line})".format(p=path, line=line))
            else:
                text_refs.append("> `{p}`".format(p=path))

        return '\n'.join(ref for ref in text_refs)
    else:
        references = item.references
        text_refs = []
        for ref_item in references:
            path = ref_item["path"]
            path = path.replace('\\', '/')  # always use unix-style paths
            text_refs.append("> '{r}'".format(r=path))
        return '\n'.join(ref for ref in text_refs)


def _format_md_links(items, linkify):
    """Format a list of linked items in Markdown."""
    links = []
    for item in items:
        link = _format_md_item_link(item, linkify=linkify)
        links.append(link)
    return ', '.join(links)


def _format_md_item_link(item, linkify=True):
    """Format an item link in Markdown."""
    if linkify and is_item(item):
        if item.header:
            return "[{h}]({p}.html#{u} \"{t}\")".format(
                u=item.uid, h=item.header, p=item.document.prefix,
                t=html.escape(item.text).replace('"', '').replace('\n', '  ')
            )
        return "[{u}]({p}.html#{u} \"{t}\")".format(u=item.uid, p=item.document.prefix,
                                                    t=html.escape(item.text)).replace('\n', '  ')
    else:
        return str(item.uid)  # if not `Item`, assume this is an `UnknownItem`


def _format_html_item_link(item, linkify=True):
    """Format an item link in HTML."""
    if linkify and is_item(item):
        if item.header:
            link = '<a href="{p}.html#{u}" title="{t}">{u} {h}</a>'.format(
                u=item.uid, h=item.header, p=item.document.prefix, t=html.escape(item.text)
            )
        else:
            link = '<a href="{p}.html#{u}" title="{t}">{u}</a>'.format(
                u=item.uid, p=item.document.prefix, t=html.escape(item.text)
            )
        return link
    else:
        return str(item.uid)  # if not `Item`, assume this is an `UnknownItem`


def _format_md_label_links(label, links, linkify):
    """Join a string of label and links with formatting."""
    if linkify:
        return "*{lb}* {ls}".format(lb=label, ls=links)
    else:
        return "*{lb} {ls}*".format(lb=label, ls=links)


def _table_of_contents_md(obj, linkify=None):
    toc = '### Table of Contents\n\n'

    for item in iter_items(obj):
        if item.depth == 1:
            prefix = ' * '
        else:
            prefix = '    ' * (item.depth - 1)
            prefix += '* '

        if item.heading:
            lines = item.text.splitlines()
            heading = lines[0] if lines else ''
        elif item.header:
            heading = "{h}".format(h=item.header)
        else:
            heading = item.uid

        if settings.PUBLISH_HEADING_LEVELS:
            level = _format_level(item.level)
            lbl = '{lev} {h}'.format(lev=level, h=heading)
        else:
            lbl = heading

        if linkify:
            line = '{p}[{lbl}](#{uid})\n'.format(p=prefix, lbl=lbl, uid=item.uid)
        else:
            line = '{p}{lbl}\n'.format(p=prefix, lbl=lbl)
        toc += line
    return toc


def _lines_html(
    obj, linkify=False, extensions=EXTENSIONS, template=HTMLTEMPLATE, toc=True
):
    """Yield lines for an HTML report.

    :param obj: Item, list of Items, or Document to publish
    :param linkify: turn links into hyperlinks

    :return: iterator of lines of text

    """
    # Determine if a full HTML document should be generated
    try:
        iter(obj)
    except TypeError:
        document = False
    else:
        document = True
    # Generate HTML

    text = '\n'.join(_lines_markdown(obj, linkify=linkify))
    body = markdown.markdown(text, extensions=extensions)

    if toc:
        toc_md = _table_of_contents_md(obj, True)
        toc_html = markdown.markdown(toc_md, extensions=extensions)
    else:
        toc_html = ''

    if document:
        try:
            bottle.TEMPLATE_PATH.insert(
                0, os.path.join(os.path.dirname(__file__), '..', 'views')
            )
            if 'baseurl' not in bottle.SimpleTemplate.defaults:
                bottle.SimpleTemplate.defaults['baseurl'] = ''
            html = bottle_template(
                template, body=body, toc=toc_html, parent=obj.parent, document=obj,
                title=f'{obj.name} - {settings.TITLE} - {settings.VERSION}'
            )
        except Exception:
            log.error("Problem parsing the template %s", template)
            raise
        yield '\n'.join(html.split(os.linesep))
    else:
        yield body


# Mapping from file extension to lines generator
FORMAT_LINES = {'.txt': _lines_text, '.md': _lines_markdown, '.html': _lines_html, '.pdf': _lines_markdown_pdf}


def check(ext):
    """Confirm an extension is supported for publish.

    :raises: :class:`doorstop.common.DoorstopError` for unknown formats

    :return: lines generator if available

    """
    exts = ', '.join(ext for ext in FORMAT_LINES)
    msg = "unknown publish format: {} (options: {})".format(ext or None, exts)
    exc = DoorstopError(msg)

    try:
        gen = FORMAT_LINES[ext]
    except KeyError:
        raise exc from None
    else:
        log.debug("found lines generator for: {}".format(ext))
        return gen
