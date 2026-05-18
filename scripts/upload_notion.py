#!/usr/bin/env python3
"""
Upload a markdown report to Notion database.
Usage: python3 upload_notion.py <md_file_path>
"""
import os, sys, re, json, urllib.request
from pathlib import Path
from datetime import datetime

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

def parse_filename(filename):
    """Extract metadata from filename. Returns dict with date, ticker, name, kind."""
    # Patterns:
    # 2026-05-17_278470_apr.md
    # 2026-05-18_020150_lotte-energy-materials_chart.md
    # 2026-05-18_daily-brief.md
    # 2026-05-18_news_NVDA_nvidia.md
    # 2026-05-18_news_sector_semiconductor.md
    # 2026-05-18_news_theme_hbm.md
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

def detect_market(ticker, content=''):
    if not ticker or ticker.lower() == 'daily-brief':
        if '한국' in content[:500] or 'KOSPI' in content[:500]:
            return '글로벌'
        return '글로벌'
    if ticker.isdigit() and len(ticker) == 6:
        # KOSPI vs KOSDAQ - approximate via first digit
        return 'KOSPI'  # 대부분 KOSPI로 분류 (정확한 판별은 외부 API 필요)
    if ticker.isalpha() and len(ticker) <= 5:
        return 'NASDAQ'  # 대부분 NASDAQ
    return '글로벌'

def extract_korean_company_name(content):
    """첫 # 헤딩에서 회사명 추출."""
    m = re.search(r'^# ([^\(\n]+?)(?:\s*\(|$)', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None

def extract_price_change(content):
    """현재가와 등락률 추출 (옵션)."""
    price = None
    change = None
    # 현재가: **404,000원** 또는 **$225.32**
    m = re.search(r'\*\*현재가\*\*\s*[:：|]\s*\*\*\$?([0-9,\.]+)', content)
    if m:
        try:
            price = float(m.group(1).replace(',', ''))
        except: pass
    # 등락률: -2.29% / +0.31%
    m = re.search(r'([+-]?[0-9\.]+)\s*%', content)
    if m:
        try:
            change = float(m.group(1)) / 100  # Notion percent format = 0.01 == 1%
        except: pass
    return price, change

def extract_tags(content):
    """본문에서 자주 등장하는 키워드로 태그 추론."""
    tags = []
    text = content.lower()
    if 'hbm' in text: tags.append('HBM')
    if '반도체' in content or '메모리' in content: 
        tags.append('반도체')
        if '메모리' in content and 'HBM' not in tags: tags.append('메모리')
    if '이차전지' in content or '배터리' in content or '2차전지' in content: tags.append('이차전지')
    if 'k뷰티' in text or '뷰티' in content or '화장품' in content: tags.append('K뷰티')
    if ' AI' in content or '인공지능' in content or 'gpu' in text: tags.append('AI')
    if '자동차' in content or '전기차' in content: tags.append('자동차')
    return list(set(tags))

def md_lines_to_blocks(text, max_blocks=95):
    """간단 마크다운 → 노션 블록 변환."""
    blocks = []
    lines = text.split('\n')
    in_code = False
    code_buffer = []
    code_lang = 'plain text'
    
    def push_paragraph(t):
        if not t.strip(): return
        # 2000자 제한
        for chunk in [t[i:i+1900] for i in range(0, len(t), 1900)]:
            blocks.append({
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
            })
    
    for line in lines:
        if len(blocks) >= max_blocks:
            break
        # 코드 블록 시작/끝
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                code_lang = line.strip()[3:].strip() or 'plain text'
                code_buffer = []
            else:
                in_code = False
                content = '\n'.join(code_buffer)[:1900]
                blocks.append({
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": content}}],
                        "language": code_lang if code_lang in ['plain text', 'python', 'bash', 'javascript', 'markdown', 'json'] else 'plain text'
                    }
                })
            continue
        if in_code:
            code_buffer.append(line)
            continue
        # 헤딩
        if line.startswith('# '):
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": [{"type":"text","text":{"content": line[2:][:1900]}}]}})
        elif line.startswith('## '):
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": [{"type":"text","text":{"content": line[3:][:1900]}}]}})
        elif line.startswith('### '):
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": [{"type":"text","text":{"content": line[4:][:1900]}}]}})
        # 인용
        elif line.startswith('> '):
            blocks.append({"type":"quote","quote":{"rich_text":[{"type":"text","text":{"content":line[2:][:1900]}}]}})
        # 불릿
        elif line.lstrip().startswith('- ') or line.lstrip().startswith('* '):
            txt = line.lstrip()[2:][:1900]
            blocks.append({"type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"type":"text","text":{"content":txt}}]}})
        # 번호
        elif re.match(r'^\d+\.\s', line):
            txt = re.sub(r'^\d+\.\s', '', line)[:1900]
            blocks.append({"type":"numbered_list_item","numbered_list_item":{"rich_text":[{"type":"text","text":{"content":txt}}]}})
        # 구분선
        elif line.strip() == '---':
            blocks.append({"type":"divider","divider":{}})
        # 빈 줄은 스킵
        elif not line.strip():
            continue
        # 일반 텍스트 (테이블 행 포함)
        else:
            push_paragraph(line)
    return blocks[:max_blocks]

def notion_request(method, url, data=None):
    req = urllib.request.Request(
        url,
        method=method,
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
    market = detect_market(meta['ticker'], content)
    price, change = extract_price_change(content)
    tags = extract_tags(content)
    
    # GitHub URL 계산
    folder = md_path.parent.name  # reports 또는 news
    github_url = f"{GITHUB_REPO_BASE}/{folder}/{md_path.name}"
    
    # 페이지 제목 만들기
    if meta['kind'] == 'Daily Brief':
        title = f"📰 {meta['date']} Daily Brief"
    elif meta['kind'] == '차트':
        title = f"📈 {company} ({meta['ticker']}) 차트분석 — {meta['date']}"
    elif meta['kind'] == '종목분석':
        title = f"📊 {company} ({meta['ticker']}) 분석 — {meta['date']}"
    else:
        title = f"📰 {company} {meta['kind']} — {meta['date']}"
    
    # 페이지 properties
    properties = {
        "이름": {"title": [{"text": {"content": title}}]},
        "분석일": {"date": {"start": meta['date']}},
        "종류": {"select": {"name": meta['kind']}},
        "GitHub": {"url": github_url},
    }
    if meta['ticker']:
        properties["티커"] = {"rich_text": [{"text": {"content": meta['ticker']}}]}
    if company:
        properties["회사명"] = {"rich_text": [{"text": {"content": company}}]}
    if market:
        properties["시장"] = {"select": {"name": market}}
    if tags:
        properties["태그"] = {"multi_select": [{"name": t} for t in tags]}
    if price is not None:
        properties["현재가"] = {"number": price}
    if change is not None:
        properties["등락률"] = {"number": change}
    
    # 본문 블록
    blocks = md_lines_to_blocks(content)
    
    # 페이지 생성
    page_data = {
        "parent": {"database_id": DB_ID},
        "properties": properties,
        "children": blocks,
    }
    
    result = notion_request("POST", "https://api.notion.com/v1/pages", page_data)
    
    if result.get('object') == 'error':
        print(f"❌ ERROR: {result.get('message')}")
        print(f"   Code: {result.get('code')}")
        sys.exit(1)
    else:
        page_url = result.get('url', 'N/A')
        print(f"✅ Uploaded: {title}")
        print(f"   Notion URL: {page_url}")
        print(f"   Properties: kind={meta['kind']}, ticker={meta['ticker']}, market={market}, tags={tags}, price={price}, change={change}")

if __name__ == "__main__":
    main()
