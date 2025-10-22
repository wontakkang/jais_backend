import asyncio
import os
import glob
import re
import json
import mimetypes
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('utils.protocol.MCU')

LOG_DIR = os.path.join(os.getcwd(), 'log')
LOG_GLOB = os.path.join(LOG_DIR, 'de_mcu*.log')
LINE_RE = re.compile(r'^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)\]\s*\[(?P<level>[^\]]+)\]\s*(?P<msg>.*)$')

LEVEL_COLORS = {
    'ERROR': 'red',
    'WARNING': 'orange',
    'INFO': 'green',
    'DEBUG': 'gray'
}
LEVEL_ICONS = {
    'ERROR': '⛔',
    'WARNING': '⚠️',
    'INFO': 'ℹ️',
    'DEBUG': '🐞'
}

HTML_UI = r'''
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DE-MCU 로그 모니터</title>
    <!-- Prefer local static copies if available -->
    <link rel="stylesheet" href="/static/ws_ui/tailwind.min.css" />
    <!-- Prefer the official local remixicon CSS (downloaded by fetch_remixicon.py) -->
    <link rel="stylesheet" href="/static/ws_ui/remixicon.full.css" />
    <!-- CDN fallbacks -->
    <script src="https://cdn.tailwindcss.com/3.4.16"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@3.4.16/dist/tailwind.min.css" />
    <!-- Minimal inline fallback styles so layout remains usable when external CSS is blocked -->
    <style>
      /* basic fallback for core layout if tailwind not loaded */
      .btn { display:inline-flex; align-items:center; gap:.5rem; padding:.5rem .9rem; border-radius:.5rem; }
      .primary{background:#2563eb;color:#fff}
      .bg-white{background:#fff}
      .bg-gray-50{background:#f9fafb}
      .bg-gray-800{background:#1f2937}
      .text-white{color:#fff}
      .rounded-lg{border-radius:.5rem}
      .shadow-sm{box-shadow:0 1px 2px rgba(0,0,0,.05)}
      table{width:100%;border-collapse:collapse}
      td, th{padding:.5rem;vertical-align:top;border-bottom:1px solid #eee}
      pre{white-space:pre-wrap;word-break:break-word;font-family:monospace}
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <!-- local or CDN remixicon -->
    <!-- if /static/ws_ui/remixicon.min.css exists it will be used, otherwise CDN fallback will be loaded above -->
    <style>
      :where([class^="ri-"])::before { content: "\f3c2"; }
      /* visual tweaks */
      .btn { border-radius: .5rem; padding: .5rem .9rem; }
      .primary { background: linear-gradient(90deg,#2563eb,#4f46e5); }
    </style>
    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              primary: "#2563eb",
              secondary: "#4f46e5",
            },
            borderRadius: {
              button: "8px",
            },
          },
        },
      };
    </script>
  </head>
  <body class="bg-gray-50 min-h-screen">
    <div class="max-w-7xl mx-auto p-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div class="bg-gray-800 text-white px-6 py-4">
          <h1 class="text-xl font-bold">DE-MCU Log (latest first)</h1>
          <div class="flex items-center gap-4 mt-2 text-sm text-gray-300">
            <span>파일: de_mcu.log</span>
            <span>라인: <span id="lineCount">200</span></span>
          </div>
        </div>

        <div class="p-4 border-b border-gray-200">
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-3">
              <button id="loadBtn" class="btn primary text-white text-sm font-medium hover:opacity-95 transition-colors">
                <i class="ri-refresh-line mr-2"></i>로드
              </button>
              <button id="connectBtn" class="btn bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors">
                <i class="ri-wifi-line mr-2"></i>연결
              </button>
              <button id="disconnectBtn" class="btn bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50" disabled>
                <i class="ri-wifi-off-line mr-2"></i>해제
              </button>
              <button id="pauseBtn" class="btn bg-yellow-600 text-white text-sm font-medium hover:bg-yellow-700 transition-colors">
                <i class="ri-pause-line mr-2"></i>정지
              </button>
              <button id="resumeBtn" class="btn bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50" disabled>
                <i class="ri-play-line mr-2"></i>재개
              </button>
            </div>

            <div class="flex items-center gap-3">
              <input id="wsToken" placeholder="WS 토큰 (선택)" class="px-3 py-2 border rounded text-sm" style="min-width:220px">
              <!-- 툴바 컨트롤(리팩토링): 반응형, wrap 허용 -->
              <div class="flex flex-wrap items-center gap-2" style="min-width:420px">
                <label class="text-xs text-gray-600 mr-2">최근</label>
                <select id="tailLinesSelect" class="px-2 py-1 border rounded text-sm" title="표시할 최근 라인 수">
                  <option value="50">50줄</option>
                  <option value="100">100줄</option>
                  <option value="200" selected>200줄</option>
                  <option value="500">500줄</option>
                  <option value="1000">1000줄</option>
                </select>
                <label class="text-xs text-gray-600 ml-2">라인</label>

                <label class="text-xs text-gray-600 ml-4">폴링(ms)</label>
                <input id="pollInterval" type="number" min="500" step="100" value="5000" class="w-20 px-2 py-1 border rounded text-sm" title="폴링 인터벌(ms)">

                <input id="keywordFilter" placeholder="키워드 필터 (스페이스/콤마 구분, /regex/ 지원)" class="px-2 py-1 border rounded text-sm" style="min-width:180px">
                <button id="applyFilterBtn" class="btn bg-gray-700 text-white text-sm">필터 적용</button>
                <button id="clearFilterBtn" class="btn bg-gray-400 text-white text-sm">필터 해제</button>
                <label class="flex items-center gap-2 text-sm text-gray-600 ml-2"><input id="autoPoll" type="checkbox"> 자동 폴링</label>
              </div>
              <label class="flex items-center gap-2 text-sm text-gray-600"><input id="autoReconnect" type="checkbox"> 자동 재연결</label>
              <div class="flex items-center gap-2">
                <div id="wsStatus" class="w-3 h-3 bg-red-500 rounded-full"></div>
                <span id="wsStatusText" class="text-sm text-gray-600">WS 연결 해제됨</span>
              </div>
            </div>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th data-col="ts" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">타임스탬프
                  <div class="mt-2 flex items-center gap-2">
                    <button class="sort-btn text-xs px-2 py-0.5 border rounded" data-col="ts">정렬</button>
                    <input id="startTs" type="datetime-local" class="text-xs px-2 py-1 border rounded" title="시작 시간">
                    <input id="endTs" type="datetime-local" class="text-xs px-2 py-1 border rounded" title="종료 시간">
                    <button id="applyTsFilter" class="text-xs px-2 py-1 border rounded">적용</button>
                    <button id="clearTsFilter" class="text-xs px-2 py-1 border rounded">해제</button>
                  </div>
                </th>
                <th data-col="level" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">레벨
                  <div class="mt-2 flex gap-1" style="flex-wrap:wrap;">
                    <span class="level-chip px-2 py-0.5 text-xs rounded border border-gray-200 bg-red-50 text-red-700" data-level="ERROR">ERROR</span>
                    <span class="level-chip px-2 py-0.5 text-xs rounded border border-gray-200 bg-yellow-50 text-yellow-700" data-level="WARNING">WARNING</span>
                    <span class="level-chip px-2 py-0.5 text-xs rounded border border-gray-200 bg-blue-50 text-blue-700" data-level="INFO">INFO</span>
                    <span class="level-chip px-2 py-0.5 text-xs rounded border border-gray-200 bg-gray-50 text-gray-700" data-level="DEBUG">DEBUG</span>
                  </div>
                </th>
                <th data-col="msg" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">메시지
                  <div class="mt-2"><button class="sort-btn text-xs px-2 py-0.5 border rounded" data-col="msg">정렬</button></div>
                </th>
              </tr>
            </thead>
            <tbody id="logTableBody" class="bg-white divide-y divide-gray-200">
            </tbody>
          </table>
        </div>

        <div class="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <div class="flex items-center justify-between text-sm text-gray-600">
            <span>총 <span id="totalLogs">0</span>개의 로그 항목</span>
            <span>마지막 업데이트: <span id="lastUpdate"></span></span>
          </div>
        </div>
      </div>
    </div>

    <script id="websocket-controls">
      </script>
    <script src="/static/ws_ui/client.js"></script>
    <noscript>
      <div style="color:#b91c1c;padding:1rem;text-align:center">자바스크립트가 비활성화되어 있습니다. UI의 전체 기능을 사용하려면 브라우저에서 JavaScript를 활성화하세요.</div>
    </noscript>
  </body>
</html>
'''


def find_latest_log_file():
    p_fixed = os.path.join(LOG_DIR, 'de_mcu.log')
    if os.path.exists(p_fixed):
        return p_fixed
    files = glob.glob(LOG_GLOB)
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


def _parse_query_string(qs_bytes):
    try:
        s = qs_bytes.decode('utf-8')
    except Exception:
        return {}
    params = {}
    for part in s.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            params[k] = v
    return params

INITIAL_TAIL_LINES = 200

# Helper: return file size / position of EOF synchronously
def init_file_pos(path):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            return f.tell()
    except Exception:
        return 0

# Helper: read new bytes from file in a thread
async def read_new_bytes(path, last_pos):
    def _read_block():
        try:
            with open(path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size <= last_pos:
                    return b'', last_pos
                f.seek(last_pos)
                data = f.read()
                new_pos = f.tell()
                return data, new_pos
        except Exception:
            return b'', last_pos
    return await asyncio.to_thread(_read_block)

# Helper: format a single log line into the payload sent over websocket
def format_log_line(line):
    m = LINE_RE.match(line)
    if m:
        ts = m.group('ts')
        level = m.group('level')
        msg = m.group('msg')
    else:
        # include milliseconds in fallback timestamp
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = 'INFO'
        msg = line
    icon = LEVEL_ICONS.get(level.upper(), '')
    summary = (msg[:200] + '...') if len(msg) > 200 else msg
    return {'type': 'line', 'ts': ts, 'level': level, 'msg': msg, 'icon': icon, 'summary': summary}

# parse timestamp string like '2025-10-14 12:32:59.609' -> milliseconds since epoch
def parse_ts_ms(ts_str):
    if not ts_str:
        return None
    try:
        # accept either 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS[.mmm]'
        s = ts_str.replace('T', ' ')
        # Try with microseconds
        try:
            dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')
        except Exception:
            dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return int(dt.timestamp() * 1000)
    except Exception:
        # fallback: try dateutil parser if available
        try:
            import importlib
            _dp = importlib.import_module('dateutil.parser')
            dt = _dp.parse(s)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

# check whether a log line matches provided filters
def _line_matches_filters(line, levels_set=None, keyword=None, keyword_regex=None, start_ms=None, end_ms=None):
    if not line or not line.strip():
        return False
    m = LINE_RE.match(line)
    if m:
        ts = m.group('ts')
        level = m.group('level')
        msg = m.group('msg')
    else:
        # try to approximate
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = 'INFO'
        msg = line
    # level filter
    if levels_set and level.upper() not in levels_set:
        return False
    # time filter
    if (start_ms is not None) or (end_ms is not None):
        ts_ms = parse_ts_ms(ts)
        if ts_ms is None:
            return False
        if start_ms is not None and ts_ms < start_ms:
            return False
        if end_ms is not None and ts_ms > end_ms:
            return False
    # keyword filter: regex has priority
    if keyword_regex:
        try:
            if not keyword_regex.search(msg):
                return False
        except Exception:
            return False
    elif keyword:
        # multi-keyword split by comma or whitespace, OR match
        terms = [t.strip().lower() for t in re.split(r'[,\s]+', keyword) if t.strip()]
        if terms:
            low = (msg or '').lower()
            matched = False
            for t in terms:
                if t in low:
                    matched = True
                    break
            if not matched:
                return False
    return True

def group_logs_by_timestamp(lines):
    """Group log lines by timestamp and merge messages with same timestamp.

    Behavior changed: if a line does not match the LINE_RE (continuation line),
    it is treated as a continuation of the previous log entry instead of creating
    a new group with a current timestamp. This preserves original multi-line
    message ordering and keeps related lines in a single column.
    """
    groups = []
    last_group = None

    for line in lines:
        if not line.strip():
            continue

        m = LINE_RE.match(line)
        if m:
            ts = m.group('ts')
            level = m.group('level')
            msg = m.group('msg')
            # start a new group
            group = {
                'ts': ts,
                'level': level,
                'messages': [msg],
                'levels': [level]
            }
            groups.append(group)
            last_group = group
        else:
            # continuation line: append to previous group's messages if exists,
            # otherwise create a synthetic group using current time
            cont = line
            if last_group is not None:
                last_group['messages'].append(cont)
            else:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                group = {
                    'ts': ts,
                    'level': 'INFO',
                    'messages': [cont],
                    'levels': ['INFO']
                }
                groups.append(group)
                last_group = group

    # Convert groups to formatted log entries preserving chronological order (oldest->newest)
    result = []
    for group in groups:
        combined_msg = '\n'.join(group['messages'])
        if len(group['messages']) > 1:
            combined_msg = f"[{len(group['messages'])}개 메시지 통합]\n{combined_msg}"
        icon = LEVEL_ICONS.get(group['level'].upper(), '')
        summary = (combined_msg[:200] + '...') if len(combined_msg) > 200 else combined_msg
        result.append({
            'type': 'line',
            'ts': group['ts'],
            'level': group['level'],
            'msg': combined_msg,
            'icon': icon,
            'summary': summary,
            'count': len(group['messages'])
        })

    return result


# helper to convert grouped entry (as returned by group_logs_by_timestamp) into payload
def format_group_entry(group_entry):
    return {
        'type': 'line',
        'ts': group_entry.get('ts'),
        'level': group_entry.get('level', 'INFO'),
        'msg': group_entry.get('msg', ''),
        'icon': LEVEL_ICONS.get(group_entry.get('level', '').upper(), ''),
        'summary': group_entry.get('summary', '')
    }

# helper to check if a grouped entry matches filters
def _group_matches_filters(group_entry, levels_set=None, keyword=None, keyword_regex=None, start_ms=None, end_ms=None):
    if not group_entry:
        return False
    ts = group_entry.get('ts')
    level = group_entry.get('level', 'INFO')
    msg = group_entry.get('msg', '')
    # level filter
    if levels_set and level.upper() not in levels_set:
        return False
    # time filter
    if (start_ms is not None) or (end_ms is not None):
        ts_ms = parse_ts_ms(ts)
        if ts_ms is None:
            return False
        if start_ms is not None and ts_ms < start_ms:
            return False
        if end_ms is not None and ts_ms > end_ms:
            return False
    # keyword / regex
    if keyword_regex:
        try:
            if not keyword_regex.search(msg):
                return False
        except Exception:
            return False
    elif keyword:
        terms = [t.strip().lower() for t in re.split(r'[,\s]+', keyword) if t.strip()]
        if terms:
            low = (msg or '').lower()
            matched = False
            for t in terms:
                if t in low:
                    matched = True
                    break
            if not matched:
                return False
    return True

def _read_tail_lines(path, n=200):
    """Read last n text lines from file path and return them as a list (oldest->newest)."""
    avg_line_size = 200
    to_read = n * avg_line_size
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0:
                return []
            seek_pos = max(0, file_size - to_read)
            f.seek(seek_pos)
            data = f.read().decode('utf-8', errors='replace')
            lines = data.splitlines()
            if seek_pos > 0 and lines:
                # drop the possibly partial first line
                lines = lines[1:]
            # return the last n lines in chronological order (oldest->newest)
            return lines[-n:]
    except Exception:
        return []

async def websocket_app(scope, receive, send):
    # Accept then authenticate using token in query string
    # helper to avoid unhandled connection reset errors when sending
    async def _safe_send(msg):
        try:
            await send(msg)
            return True
        except (ConnectionResetError, OSError):
            return False
        except Exception:
            # catch-all to keep the loop stable
            return False

    # helper to receive and treat transport errors as disconnect
    async def _safe_receive():
        try:
            return await receive()
        except (ConnectionResetError, OSError):
            return {'type': 'websocket.disconnect'}
        except Exception:
            return {'type': 'websocket.disconnect'}

    if not await _safe_send({'type': 'websocket.accept'}):
        return
    params = _parse_query_string(scope.get('query_string', b''))
    token = params.get('token')
    # support 'file' query parameter (basename only) to select specific log file
    requested_file = params.get('file')
    expected = getattr(settings, 'DE_MCU_WS_TOKEN', None)
    if expected is not None:
        if token != expected:
            # send error and close
            await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type':'error','msg':'Unauthorized'})})
            await _safe_send({'type': 'websocket.close', 'code': 4003})
            return

    poll_interval = 0.5
    last_size = 0
    # if client requested a specific basename, validate and use it
    current_path = None
    if requested_file:
        try:
            # prevent path traversal: only allow basename without separators
            if os.path.basename(requested_file) != requested_file:
                current_path = None
            else:
                candidate = os.path.join(LOG_DIR, requested_file)
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    current_path = candidate
        except Exception:
            current_path = None
    if current_path is None:
        current_path = find_latest_log_file()
    # logger.debug('websocket_app: found log file: %s', current_path)
    if not current_path:
        await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type':'error','msg':'No log file found'})})
        # wait for disconnect
        while True:
            event = await _safe_receive()
            if event.get('type') == 'websocket.disconnect':
                return

    # initialize last_size by querying file size
    last_size = await asyncio.to_thread(init_file_pos, current_path)
    # logger.debug('websocket_app: initial last_size=%d for %s', last_size, current_path)
    # connection-specific active filters (None = no filter)
    conn_levels = None
    conn_keyword = None
    conn_keyword_regex = None
    conn_start_ms = None
    conn_end_ms = None

    # send recent tail lines so client sees history on connect (respect filters if previously set)
    try:
        tail_lines = await asyncio.to_thread(_read_tail_lines, current_path, INITIAL_TAIL_LINES)
        # group tail lines into entries preserving multi-line messages
        grouped = group_logs_by_timestamp(tail_lines)
        for entry in grouped:
            if not entry:
                continue
            # if filters set, apply; otherwise send all
            if conn_levels or conn_keyword or conn_keyword_regex or conn_start_ms or conn_end_ms:
                if not _group_matches_filters(entry, conn_levels, conn_keyword, conn_keyword_regex, conn_start_ms, conn_end_ms):
                    continue
            payload = format_group_entry(entry)
            if not await _safe_send({'type': 'websocket.send', 'text': json.dumps(payload)}):
                logger.debug('websocket_app: 초기 테일 페이로드 전송 실패, 연결 종료')
                return
    except Exception:
        logger.exception('websocket_app: 초기 테일 전송 중 예외 발생')

    # 메인 루프: 클라이언트 명령에 응답하고 파일 변경사항을 테일링
    try:
        while True:
            # 파일 폴링도 할 수 있도록 타임아웃과 함께 클라이언트 메시지 확인
            event = None
            try:
                event = await asyncio.wait_for(_safe_receive(), timeout=poll_interval)
            except asyncio.TimeoutError:
                event = None

            if event:
                if event.get('type') == 'websocket.disconnect':
                    logger.debug('websocket_app: 클라이언트 연결 해제됨')
                    return
                if event.get('type') == 'websocket.receive':
                    text = event.get('text')
                    if text:
                        try:
                            msg = json.loads(text)
                        except Exception:
                            msg = None
                        if isinstance(msg, dict) and msg.get('cmd') == 'reload_tail':
                            # allow client to request specific number of lines and optional keyword filter
                            lines = int(msg.get('lines') or INITIAL_TAIL_LINES)
                            keyword = msg.get('keyword')
                            # allow changing the tailed file while connected via 'file' (basename only)
                            req_file = msg.get('file')
                            if req_file:
                                try:
                                    if os.path.basename(req_file) == req_file:
                                        cand = os.path.join(LOG_DIR, req_file)
                                        if os.path.exists(cand) and os.path.isfile(cand):
                                            # switch current path and reset last_size
                                            current_path = cand
                                            last_size = await asyncio.to_thread(init_file_pos, current_path)
                                            # notify client about successful switch
                                            await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type': 'info', 'msg': f'Switched to {req_file}'})})
                                        else:
                                            # invalid file: notify client and continue (do not change current_path)
                                            await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type':'error','msg':'Requested file not found'})})
                                            # skip further reload handling for invalid file
                                            continue
                                    else:
                                        await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type':'error','msg':'Invalid file name'})})
                                        continue
                                except Exception:
                                    await _safe_send({'type': 'websocket.send', 'text': json.dumps({'type':'error','msg':'Error resolving requested file'})})
                                    continue
                            level_param = msg.get('levels') or msg.get('level')
                            start_param = msg.get('start') or msg.get('startTs')
                            end_param = msg.get('end') or msg.get('endTs')

                            # update connection filters
                            conn_levels = None
                            if level_param:
                                try:
                                    if isinstance(level_param, (list, tuple)):
                                        conn_levels = set([l.upper() for l in level_param if l])
                                    else:
                                        conn_levels = set([l.strip().upper() for l in re.split(r'[,\s]+', str(level_param)) if l.strip()])
                                except Exception:
                                    conn_levels = None

                            conn_keyword = None
                            conn_keyword_regex = None
                            if keyword:
                                k = str(keyword).strip()
                                if len(k) >= 2 and k.startswith('/') and k.endswith('/'):
                                    try:
                                        conn_keyword_regex = re.compile(k[1:-1])
                                    except Exception:
                                        conn_keyword_regex = None
                                else:
                                    conn_keyword = k

                            conn_start_ms = None
                            conn_end_ms = None
                            try:
                                if start_param:
                                    # accept epoch ms or datetime-local / ISO
                                    try:
                                        conn_start_ms = int(start_param)
                                    except Exception:
                                        conn_start_ms = parse_ts_ms(str(start_param))
                                if end_param:
                                    try:
                                        conn_end_ms = int(end_param)
                                    except Exception:
                                        conn_end_ms = parse_ts_ms(str(end_param))
                            except Exception:
                                conn_start_ms = None
                                conn_end_ms = None

                            try:
                                tail_lines = await asyncio.to_thread(_read_tail_lines, current_path, lines)
                                grouped = group_logs_by_timestamp(tail_lines)
                                for entry in grouped:
                                    if not entry:
                                        continue
                                    if not _group_matches_filters(entry, conn_levels, conn_keyword, conn_keyword_regex, conn_start_ms, conn_end_ms):
                                        continue
                                    payload = format_group_entry(entry)
                                    if not await _safe_send({'type': 'websocket.send', 'text': json.dumps(payload)}):
                                        logger.debug('websocket_app: 테일 페이로드 전송 실패, 연결 종료')
                                        return
                            except Exception:
                                logger.exception('websocket_app: 리로드 명령에서 테일 전송 중 예외 발생')
            # 현재 로그 파일이 회전/변경되었는지 감지
            latest = find_latest_log_file()
            if latest != current_path and latest is not None:
                logger.debug('websocket_app: 로그 파일이 %s에서 %s로 전환됨', current_path, latest)
                current_path = latest
                last_size = await asyncio.to_thread(init_file_pos, current_path)

            # last_size 이후의 새로운 바이트 읽기
            data, new_pos = await read_new_bytes(current_path, last_size)
            if new_pos < last_size:
                # 파일이 잘리거나 회전됨: 위치 재설정
                last_size = await asyncio.to_thread(init_file_pos, current_path)
            elif data:
                try:
                    text = data.decode('utf-8', errors='replace')
                    lines = text.splitlines()
                    # 멀티라인 메시지가 결합되도록 들어오는 라인들을 그룹화
                    grouped = group_logs_by_timestamp(lines)
                    for entry in grouped:
                        if not entry or not entry.get('msg'):
                            continue
                        # 연결 필터가 있으면 적용
                        if not _group_matches_filters(entry, conn_levels, conn_keyword, conn_keyword_regex, conn_start_ms, conn_end_ms):
                            continue
                        payload = format_group_entry(entry)
                        if not await _safe_send({'type': 'websocket.send', 'text': json.dumps(payload)}):
                            logger.debug('websocket_app: 페이로드 전송 실패, 연결 종료')
                            return
                except Exception:
                    logger.exception('websocket_app: 새로운 바이트 처리 중 오류')
                last_size = new_pos
    except Exception:
        logger.exception('websocket_app: 예상치 못한 예외 발생')
    finally:
        try:
            await _safe_send({'type': 'websocket.close'})
        except Exception:
            pass


# Serve static files for the embedded UI under /static/ws_ui/
async def static_file_app(scope, receive, send):
    path = scope.get('path', '')
    prefix = '/static/ws_ui/'
    if scope.get('type') != 'http' or not path.startswith(prefix):
        await send({'type': 'http.response.start', 'status': 404, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'Not Found', 'more_body': False})
        return

    rel = path[len(prefix):]
    root = os.path.join(os.getcwd(), 'utils', 'static', 'ws_ui')
    full_path = os.path.normpath(os.path.join(root, rel))
    # prevent path traversal
    try:
        root_abs = os.path.abspath(root)
        full_abs = os.path.abspath(full_path)
    except Exception:
        full_abs = full_path
        root_abs = root
    if not full_abs.startswith(root_abs):
        await send({'type': 'http.response.start', 'status': 403, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'Forbidden', 'more_body': False})
        return

    if not os.path.exists(full_abs) or not os.path.isfile(full_abs):
        await send({'type': 'http.response.start', 'status': 404, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'Not Found', 'more_body': False})
        return

    mime_type, _ = mimetypes.guess_type(full_abs)
    if not mime_type:
        mime_type = 'application/octet-stream'
    try:
        def _read():
            with open(full_abs, 'rb') as f:
                return f.read()
        body = await asyncio.to_thread(_read)
        headers = [(b'content-type', mime_type.encode('utf-8')), (b'content-length', str(len(body)).encode('utf-8'))]
        await send({'type': 'http.response.start', 'status': 200, 'headers': headers})
        await send({'type': 'http.response.body', 'body': body, 'more_body': False})
    except Exception:
        await send({'type': 'http.response.start', 'status': 500, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
        await send({'type': 'http.response.body', 'body': b'Internal Server Error', 'more_body': False})
        return


# Simple HTTP app for serving UI and API endpoints
async def http_app(scope, receive, send):
    # static assets
    if scope.get('path', '').startswith('/static/ws_ui/'):
        return await static_file_app(scope, receive, send)

    # API: return latest tail lines as JSON
    if scope.get('path', '') == '/api/de-mcu-tail':
        if scope.get('method', 'GET').upper() != 'GET':
            await send({'type': 'http.response.start', 'status': 405, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
            await send({'type': 'http.response.body', 'body': b'Method Not Allowed', 'more_body': False})
            return
        current_path = find_latest_log_file()
        if not current_path:
            body = json.dumps({'error': 'No log file found'}).encode('utf-8')
            await send({'type': 'http.response.start', 'status': 404, 'headers': [(b'content-type', b'application/json; charset=utf-8'), (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})
            return
        try:
            qs = _parse_query_string(scope.get('query_string', b''))
            lines_num = int(qs.get('lines') or INITIAL_TAIL_LINES)
            keyword = qs.get('keyword')
            level_param = qs.get('level') or qs.get('levels')
            start_param = qs.get('start') or qs.get('startTs') or qs.get('start_ts')
            end_param = qs.get('end') or qs.get('endTs') or qs.get('end_ts')

            conn_levels = None
            if level_param:
                try:
                    conn_levels = set([l.strip().upper() for l in re.split(r'[,\s]+', str(level_param)) if l.strip()])
                except Exception:
                    conn_levels = None

            conn_keyword = None
            conn_keyword_regex = None
            if keyword:
                k = str(keyword).strip()
                if len(k) >= 2 and k.startswith('/') and k.endswith('/'):
                    try:
                        conn_keyword_regex = re.compile(k[1:-1])
                    except Exception:
                        conn_keyword_regex = None
                else:
                    conn_keyword = k

            conn_start_ms = None
            conn_end_ms = None
            try:
                if start_param:
                    try:
                        conn_start_ms = int(start_param)
                    except Exception:
                        conn_start_ms = parse_ts_ms(str(start_param))
                if end_param:
                    try:
                        conn_end_ms = int(end_param)
                    except Exception:
                        conn_end_ms = parse_ts_ms(str(end_param))
            except Exception:
                conn_start_ms = None
                conn_end_ms = None

            raw_lines = await asyncio.to_thread(_read_tail_lines, current_path, lines_num)
            # group raw lines into combined entries
            grouped = group_logs_by_timestamp(raw_lines)
            if conn_keyword or conn_keyword_regex or conn_levels or conn_start_ms or conn_end_ms:
                grouped = [g for g in grouped if _group_matches_filters(g, conn_levels, conn_keyword, conn_keyword_regex, conn_start_ms, conn_end_ms)]
            payloads = [format_group_entry(g) for g in grouped if g]
            body = json.dumps(payloads).encode('utf-8')
            headers = [(b'content-type', b'application/json; charset=utf-8'), (b'content-length', str(len(body)).encode())]
            await send({'type': 'http.response.start', 'status': 200, 'headers': headers})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})
            return
        except Exception:
            body = json.dumps({'error': 'Internal Server Error'}).encode('utf-8')
            await send({'type': 'http.response.start', 'status': 500, 'headers': [(b'content-type', b'application/json; charset=utf-8'), (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})
            return

    # serve UI HTML
    if scope.get('path', '') in ('/', '/ui', '/logs'):
        body = HTML_UI.encode('utf-8')
        headers = [(b'content-type', b'text/html; charset=utf-8'), (b'content-length', str(len(body)).encode())]
        await send({'type': 'http.response.start', 'status': 200, 'headers': headers})
        await send({'type': 'http.response.body', 'body': body, 'more_body': False})
        return

    # fallback: 404
    await send({'type': 'http.response.start', 'status': 404, 'headers': [(b'content-type', b'text/plain; charset=utf-8')]})
    await send({'type': 'http.response.body', 'body': b'Not Found', 'more_body': False})
