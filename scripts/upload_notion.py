#!/usr/bin/env python3
"""Upload a markdown report to Notion database with proper table + inline formatting."""
import os, sys, re, json, urllib.request, urllib.error
from pathlib import Path

# Auto-load .env if exists
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB_ID = os.environ.get("NOTION_DB_ID", "364a83b218df808ea27fec1aad14532d")
GITHUB_REPO_BASE = "https://github.com/saewoomk88/stock/blob/main"

if not NOTION_TOKEN:
    print("ERROR: NOTION_TOKEN env var required")
    sys.exit(1)

# === 인라인 마크다운 → Notion rich_text 변환 ===
def inline_to_richtext(text, max_len=1900):
    """**bold**, [link](url), `code` 처리 → rich_text 배열."""
    text = text[:max_len]
    pattern = re.compile(
        r'(\*\*[^*\n]+?\*\*)'       # **bold**
        r'|(\[[^\]\n]+?\]\([^\)\n]+?\))'  # [link](url)
        r'|(`[^`\n]+?`)'             # `code`
    )
    parts = []
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            parts.append({"type": "text", "text": {"content": text[last:m.start()]}})
        token = m.group(0)
        if token.startswith('**'):
            parts.append({
                "type": "text",
                "text": {"content": token[2:-2]},
                "annotations": {"bold": True}
            })
        elif token.startswith('['):
            mm = re.match(r'\[([^\]]+)\]\(([^\)]+)\)', token)
            if mm:
                parts.append({
                    "type": "text",
                    "text": {"content": mm.group(1), "link": {"url": mm.group(2)}}
                })
        elif token.startswith('`'):
            parts.append({
                "type": "text",
                "text": {"content": token[1:-1]},
                "annotations": {"code": True}
            })
        last = m.end()
    if last < len(text):
        parts.append({"type": "text", "text": {"content": text[last:]}})
    return parts if parts else [{"type": "text", "text": {"content": text}}]


def cell_to_richtext(cell_text):
    """테이블 셀 텍스트 → rich_text (인라인 포맷 포함)."""
    return inline_to_richtext(cell_text.strip(), max_len=1900)


def parse_table(lines, start_idx):
    """마크다운 테이블 파싱. (table_block, next_idx) 반환."""
    rows = []
    i = start_idx
    while i < len(lines) and lines[i].strip().startswith('|'):
        line = lines[i].strip()
        # 구분 행 (|---|---|...) 스킵
        if re.match(r'^\|[\s\-:|]+\|?\s*$', line):
            i += 1
            continue
        # 셀 분리: 양 끝 | 제거 후 | 로 split
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)
        i += 1
    
    if not rows:
        return None, start_idx
    
    width = max(len(r) for r in rows)
    # 짧은 행은 빈 셀로 패딩
    rows = [r + [''] * (width - len(r)) for r in rows]
    
    table_block = {
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                {
                    "type": "table_row",
                    "table_row": {
                        "cells": [cell_to_richtext(cell) for cell in row]
                    }
                }
                for row in rows
            ]
        }
    }
    return table_block, i


# === 메타데이터 추출 ===
def parse_filename(filename):
    stem = Path(filename).stem
    parts = stem.split('_')
    meta = {'date': parts[0], 'ticker': '', 'company': '', 'kind': '종목분석'}
    
    if 'daily-brief' in stem:
        meta['kind'] = 'Daily Brief'
        meta['company'] = '한국·미국 시장 종합'
    elif 'news_sector' in stem:
        meta['kind'] = '섹터뉴스'
        meta['company'] = '_'.join(parts[3:]) if len(parts) > 3 else ''
    elif 'news_theme' in stem:
        meta['kind'] = '테마뉴스'
        meta['company'] = '_'.join(parts[3:]) if len(parts) > 3 else ''
    elif 'news_' in stem:
        meta['kind'] = '종목뉴스'
        meta['ticker'] = parts[2] if len(parts) > 2 else ''
        meta['company'] = '_'.join(parts[3:]) if len(parts) > 3 else ''
    elif '_chart' in stem:
        meta['kind'] = '차트'
        meta['ticker'] = parts[1]
        meta['company'] = '_'.join(parts[2:-1])
    else:
        meta['kind'] = '종목분석'
        meta['ticker'] = parts[1] if len(parts) > 1 else ''
        meta['company'] = '_'.join(parts[2:]) if len(parts) > 2 else ''
    return meta


def detect_market(ticker):
    if not ticker: return '글로벌'
    if ticker.isdigit() and len(ticker) == 6: return 'KOSPI'
    if ticker.isalpha() and len(ticker) <= 5: return 'NASDAQ'
    return '글로벌'


def extract_korean_company_name(content):
    m = re.search(r'^# ([^\(\n]+?)(?:\s*\(|$)', content, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_price_change(content):
    price = None
    change = None
    m = re.search(r'\*\*현재가\*\*\s*[:：|]\s*\*\*\$?([0-9,\.]+)', content)
    if m:
        try: price = float(m.group(1).replace(',', ''))
        except: pass
    m = re.search(r'([+-]?[0-9\.]+)\s*%', content)
    if m:
        try: change = float(m.group(1)) / 100
        except: pass
    return price, change


def extract_tags(content):
    tags = []
    text = content.lower()
    if 'hbm' in text: tags.append('HBM')
    if '반도체' in content or '메모리' in content:
        tags.append('반도체')
        if '메모리' in content and 'HBM' not in tags: tags.append('메모리')
    if '이차전지' in content or '2차전지' in content: tags.append('이차전지')
    if 'k뷰티' in text or '화장품' in content: tags.append('K뷰티')
    if ' AI' in content or '인공지능' in content or 'gpu' in text: tags.append('AI')
    if '자동차' in content or '전기차' in content: tags.append('자동차')
    return list(set(tags))


# === 마크다운 → 블록 변환 (테이블 지원) ===
def md_to_blocks(text, max_blocks=95):
    blocks = []
    lines = text.split('\n')
    i = 0
    in_code = False
    code_buffer = []
    code_lang = 'plain text'
    
    valid_langs = {'plain text', 'python', 'bash', 'javascript', 'markdown', 'json', 'shell', 'html', 'css', 'sql'}
    
    while i < len(lines) and len(blocks) < max_blocks:
        line = lines[i]
        
        # 코드 블록
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                code_lang = line.strip()[3:].strip() or 'plain text'
                if code_lang not in valid_langs:
                    code_lang = 'plain text'
                code_buffer = []
            else:
                in_code = False
                content_code = '\n'.join(code_buffer)[:1900]
                blocks.append({
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": content_code}}],
                        "language": code_lang
                    }
                })
            i += 1
            continue
        if in_code:
            code_buffer.append(line)
            i += 1
            continue
        
        # 테이블 (| 로 시작하는 연속 라인)
        if line.strip().startswith('|') and not line.strip().startswith('|---'):
            table_block, next_i = parse_table(lines, i)
            if table_block:
                blocks.append(table_block)
                i = next_i
                continue
        
        # 헤딩
        if line.startswith('# '):
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": inline_to_richtext(line[2:])}})
        elif line.startswith('## '):
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": inline_to_richtext(line[3:])}})
        elif line.startswith('### '):
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": inline_to_richtext(line[4:])}})
        # 인용
        elif line.startswith('> '):
            blocks.append({"type": "quote", "quote": {"rich_text": inline_to_richtext(line[2:])}})
        # 불릿
        elif line.lstrip().startswith('- ') or line.lstrip().startswith('* '):
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": inline_to_richtext(line.lstrip()[2:])}})
        # 번호 리스트
        elif re.match(r'^\d+\.\s', line):
            txt = re.sub(r'^\d+\.\s', '', line)
            blocks.append({"type": "numbered_list_item", "numbered_list_item": {"rich_text": inline_to_richtext(txt)}})
        # 구분선
        elif line.strip() == '---':
            blocks.append({"type": "divider", "divider": {}})
        # 빈 줄 스킵
        elif not line.strip():
            pass
        # 일반 텍스트
        else:
            blocks.append({"type": "paragraph", "paragraph": {"rich_text": inline_to_richtext(line)}})
        
        i += 1
    
    return blocks[:max_blocks]


# === Notion API ===
def notion_request(method, url, data=None):
    req = urllib.request.Request(
        url, method=method,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        data=json.dumps(data).encode() if data else None
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def main():
    if len(sys.argv) < 2:
        print("Usage: upload_notion.py <md_file_path>")
        sys.exit(1)
    
    md_path = Path(sys.argv[1]).expanduser().resolve()
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        sys.exit(1)
    
    content = md_path.read_text()
    meta = parse_filename(md_path.name)
    company = extract_korean_company_name(content) or meta['company']
    market = detect_market(meta['ticker'])
    price, change = extract_price_change(content)
    tags = extract_tags(content)
    
    folder = md_path.parent.name
    github_url = f"{GITHUB_REPO_BASE}/{folder}/{md_path.name}"
    
    # 페이지 제목
    if meta['kind'] == 'Daily Brief':
        title = f"📰 {meta['date']} Daily Brief"
    elif meta['kind'] == '차트':
        title = f"📈 {company} ({meta['ticker']}) 차트분석 — {meta['date']}"
    elif meta['kind'] == '종목분석':
        title = f"📊 {company} ({meta['ticker']}) 분석 — {meta['date']}"
    else:
        title = f"📰 {company} {meta['kind']} — {meta['date']}"
    
    properties = {
        "이름": {"title": [{"text": {"content": title}}]},
        "분석일": {"date": {"start": meta['date']}},
        "종류": {"select": {"name": meta['kind']}},
        "GitHub": {"url": github_url},
    }
    if meta['ticker']: properties["티커"] = {"rich_text": [{"text": {"content": meta['ticker']}}]}
    if company: properties["회사명"] = {"rich_text": [{"text": {"content": company}}]}
    if market: properties["시장"] = {"select": {"name": market}}
    if tags: properties["태그"] = {"multi_select": [{"name": t} for t in tags]}
    if price is not None: properties["현재가"] = {"number": price}
    if change is not None: properties["등락률"] = {"number": change}
    
    blocks = md_to_blocks(content)
    
    result = notion_request("POST", "https://api.notion.com/v1/pages", {
        "parent": {"database_id": DB_ID},
        "properties": properties,
        "children": blocks,
    })
    
    if result.get('object') == 'error':
        print(f"❌ ERROR: {result.get('message')}")
        sys.exit(1)
    print(f"✅ Uploaded: {title}")
    print(f"   Notion URL: {result.get('url', 'N/A')}")
    print(f"   Blocks: {len(blocks)}, Tables: {sum(1 for b in blocks if b['type']=='table')}")


if __name__ == "__main__":
    main()
