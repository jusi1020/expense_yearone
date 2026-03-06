from flask import Flask, render_template, request, send_file, jsonify
from pypdf import PdfWriter, PdfReader
from PIL import Image
from datetime import datetime
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# ─── 비용 유형 정의 ────────────────────────────────────────────────────────────
# category / category_icon : 그룹핑에 사용
# icon : 카드에 표시
# documents : 업로드 항목 목록
EXPENSE_TYPES = {

    # ── 1. 연구시설·장비비 및 연구재료비 ─────────────────────────────────────────
    'equipment_consumables': {
        'name': '소모품·비소모품 구매',
        'category': '연구시설·장비비 및 연구재료비',
        'category_icon': '🔬',
        'icon': '📦',
        'documents': [
            {'id': 'receipt',       'name': '카드매출전표 또는 세금계산서',        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',    'name': '검수내역(검수조서)',                   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'deliberation',  'name': '심의승인 문서 (3천만원 이상)',         'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'import_docs',   'name': '수입신고 서류 (외자구매)',             'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'delivery',      'name': '납품서(거래명세서)',                   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'equipment_service': {
        'name': '용역·공사',
        'category': '연구시설·장비비 및 연구재료비',
        'category_icon': '🔬',
        'icon': '🏗️',
        'documents': [
            {'id': 'receipt',              'name': '카드매출전표 또는 세금계산서',  'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',           'name': '검수내역(검수조서)',             'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'deliberation',         'name': '심의승인 문서 (3천만원 이상)',   'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'import_docs',          'name': '수입신고 서류 (외자구매)',       'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'task_order',           'name': '과업지시서',                    'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'spec',                 'name': '시방서 (공사)',                  'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'quote',                'name': '견적서',                        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'acceptance',           'name': '승낙사항',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'completion',           'name': '완료보고서(완료계)',             'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'construction_photos',  'name': '공사사진',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'central_purchase_equipment': {
        'name': '중앙구매 - 연구장비 (100만원↑)',
        'category': '연구시설·장비비 및 연구재료비',
        'category_icon': '🔬',
        'icon': '🖥️',
        'documents': [
            {'id': 'purchase_req',     'name': '구매요구서 (ERP시스템 등록)',   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'spec_doc',         'name': '규격서 (비소모품)',              'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'consumable_desc',  'name': '소모품용도설명서 (소모품)',      'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'quote',            'name': '견적서',                        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'acceptance',       'name': '승낙사항',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'delivery',         'name': '납품서(거래명세서)',             'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'tax_invoice',      'name': '세금계산서 (청구용)',            'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'item_photos',      'name': '물품사진',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'central_purchase_reagent': {
        'name': '중앙구매 - 시약·재료 (300만원↑)',
        'category': '연구시설·장비비 및 연구재료비',
        'category_icon': '🔬',
        'icon': '🧪',
        'documents': [
            {'id': 'purchase_req',     'name': '구매요구서 (ERP시스템 등록)',   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'spec_doc',         'name': '규격서 (비소모품)',              'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'consumable_desc',  'name': '소모품용도설명서 (소모품)',      'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'quote',            'name': '견적서',                        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'acceptance',       'name': '승낙사항',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'delivery',         'name': '납품서(거래명세서)',             'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'tax_invoice',      'name': '세금계산서 (청구용)',            'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'item_photos',      'name': '물품사진',                      'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'central_purchase_service': {
        'name': '중앙구매 - 용역·공사 (1,000만원↑)',
        'category': '연구시설·장비비 및 연구재료비',
        'category_icon': '🔬',
        'icon': '🏢',
        'documents': [
            {'id': 'purchase_req',         'name': '구매요구서 (ERP시스템 등록)',  'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'task_order',           'name': '과업지시서',                   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'spec',                 'name': '시방서 (공사)',                 'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'quote',                'name': '견적서',                       'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'acceptance',           'name': '승낙사항',                     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'completion',           'name': '완료보고서(완료계)',            'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'construction_photos',  'name': '공사사진',                     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },

    # ── 2. 연구활동비 ─────────────────────────────────────────────────────────────
    'ip_creation': {
        'name': '지식재산창출활동비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '💡',
        'documents': [
            {'id': 'receipt',       'name': '카드매출전표 또는 세금계산서',        'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'delivery',      'name': '납품서(거래명세서)',                   'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',    'name': '검수내역(검수조서)',                   'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'result_report', 'name': '지식재산 창출 결과보고서',             'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'tech_introduction': {
        'name': '기술도입비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🔧',
        'documents': [
            {'id': 'receipt',    'name': '카드매출전표 또는 세금계산서', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection', 'name': '검수내역(검수조서)',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'contract',   'name': '기술도입계약서',               'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'expert_utilization': {
        'name': '전문가활용비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '👨‍🏫',
        'documents': [
            {'id': 'expert_form',      'name': '전문가활용내역서, 특강료 영수증',             'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'lecture_proof',    'name': '강의자료, 강의사진/화면, 출석부 등',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'id_docs',          'name': '이력서, 신분증, 통장사본',                    'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'sex_crime_check',  'name': '성범죄경력조회 회신서 (강사료)',               'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'rd_service': {
        'name': '연구개발서비스활용비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🔭',
        'documents': [
            {'id': 'receipt',       'name': '카드매출전표 또는 세금계산서',          'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'usage_details', 'name': '사용내역서',                           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'result_report', 'name': '연구개발서비스 결과서 (시험분석결과서 등)', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'meeting_fee': {
        'name': '회의비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🤝',
        'documents': [
            {'id': 'receipt',       'name': '카드매출전표',              'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'minutes',       'name': '회의록 (ERP시스템 등록)',    'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'meeting_plan',  'name': '회의계획서 (필요시)',        'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'seminar_fee': {
        'name': '회의·세미나개최비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🎤',
        'documents': [
            {'id': 'receipt',        'name': '카드매출전표 또는 세금계산서',          'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'seminar_report', 'name': '세미나 정산 보고서, 특강료 영수증',     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'seminar_plan',   'name': '세미나 개최 계획서',                   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'lecture_proof',  'name': '강의자료, 강의사진 등 (필요시)',        'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'minutes',        'name': '내부결재 문서 또는 회의록',             'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'domestic_trip': {
        'name': '국내출장비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🚆',
        'documents': [
            {'id': 'app_prof',    'name': '출장신청서 (교수님)',                        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'app_student', 'name': '출장신청서 (학생)',                          'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'transport',   'name': '교통비 증빙',                               'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'accommodation','name': '숙박비 증빙',                              'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'proof',       'name': '출장 증빙 (학회프로그램/회의록/사진 등)',   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'travel_calc', 'name': '여비산출내역서 등 (필요시)',                'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'overseas_trip': {
        'name': '국외출장비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '✈️',
        'documents': [
            {'id': 'app_prof',       'name': '출장신청서 (교수님)',                              'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'app_student',    'name': '출장신청서 (학생)',                                'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'overseas_plan',  'name': '공무국외출장계획서 (부실학회 자가점검표 포함)',     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'transport',      'name': '교통비 증빙 (e티켓, 보딩패스)',                   'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'accommodation',  'name': '숙박비 증빙',                                    'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'proof1',         'name': '관련 증빙 (학회프로그램/회의록/사진 등)',          'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'proof2',         'name': '관련 증빙2 (환율표, 논문초록, 출입국증명 등)',     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'result_report',  'name': '공무국외출장결과보고서',                          'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'travel_calc',    'name': '여비산출내역서 등 (필요시)',                       'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'software': {
        'name': '소프트웨어활용비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '💻',
        'documents': [
            {'id': 'receipt',    'name': '카드매출전표 또는 세금계산서', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection', 'name': '검수내역(검수조서)',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'cloud': {
        'name': '클라우드컴퓨팅서비스활용비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '☁️',
        'documents': [
            {'id': 'internal_approval', 'name': '내부결재문서 (분담내역 포함)', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',        'name': '검수내역(검수조서)',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'lab_operation': {
        'name': '연구실운영비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🏛️',
        'documents': [
            {'id': 'receipt',       'name': '카드매출전표 또는 세금계산서', 'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',    'name': '검수내역(검수조서)',           'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'purpose_desc',  'name': '용도설명서 (필요시)',          'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'education_training': {
        'name': '교육훈련비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🎓',
        'documents': [
            {'id': 'receipt',          'name': '카드매출전표 또는 세금계산서',    'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'edu_receipt',      'name': '교육기관 발급 교육비 수납영수증', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'completion_cert',  'name': '교육수료증',                     'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'conference_fee': {
        'name': '학회·세미나참가비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🏅',
        'documents': [
            {'id': 'receipt',             'name': '카드매출전표 또는 세금계산서',              'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'registration_receipt','name': '학회등록비 영수증',                        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'conference_proof',    'name': '학회 관련 증빙 (세부일정, 명찰, 참가증 등)', 'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'payment_form',        'name': '지급신청서 (필요시)',                       'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'overtime_meal': {
        'name': '야근·특근식대',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🍱',
        'documents': [
            {'id': 'receipt',         'name': '카드매출전표',          'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'overtime_record', 'name': '시간외근무 확인대장',   'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'overseas_researcher': {
        'name': '해외연구자 유치 지원비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '🌍',
        'documents': [
            {'id': 'internal_approval', 'name': '내부결재문서 (지원대상자 자격요건 포함)', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'receipt',           'name': '카드매출전표 또는 세금계산서',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'stay_proof',        'name': '체제비 관련 증빙',                      'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'comprehensive_mgmt': {
        'name': '종합사업관리비',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '📊',
        'documents': [
            {'id': 'internal_approval', 'name': '내부결재문서 (연구인프라 조성 이행계획)', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'receipt',           'name': '카드매출전표 또는 세금계산서',           'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',        'name': '검수내역(검수조서)',                    'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'expert_form',       'name': '전문가 활용내역서',                    'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'other_expenses': {
        'name': '그 밖의 비용',
        'category': '연구활동비',
        'category_icon': '📚',
        'icon': '📋',
        'documents': [
            {'id': 'receipt',           'name': '카드매출전표 또는 세금계산서',              'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'inspection',        'name': '검수내역(검수조서)',                       'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'paper_form',        'name': '논문게재료 신청서, 부실학회 체크리스트',   'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'internal_approval', 'name': '내부결재문서',                            'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'payment_form',      'name': '지급신청서, 지급명세서 (필요시)',          'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },

    # ── 3. 연구수당 ──────────────────────────────────────────────────────────────
    'research_allowance': {
        'name': '연구수당',
        'category': '연구수당',
        'category_icon': '💰',
        'icon': '💰',
        'documents': [
            {'id': 'allowance_form',  'name': '연구수당 신청서',    'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'evaluation_form', 'name': '연구수당지급 평가서', 'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
}
# ───────────────────────────────────────────────────────────────────────────────


_EQUIPMENT_DESC = """
<h6>📌 사용용도</h6>
<ul>
  <li><strong>구입·설치비:</strong> 연구시설·장비의 구입·설치비, 관련 부대비용 또는 성능향상비</li>
  <li><strong>임차비:</strong> 연구시설·장비의 임차비</li>
  <li><strong>운영·유지비:</strong> 유지·보수비·운영비 또는 이전 설치비</li>
  <li><strong>연구인프라 조성비:</strong> 부지·시설의 매입·임차·조성비, 설계·건축·감리비 또는 장비 구입·설비비</li>
</ul>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>본교에서 보유 또는 생산하여 자산으로 등록하는 연구시설·장비는 <strong>구입가(부대비용 포함)</strong>로 계상</li>
  <li>3천만원 이상 연구시설·장비는 국가연구시설장비 심의위원회 심의 대상</li>
  <li>원래 계획에 반영되지 않은 <strong>3천만원 이상의 연구시설·장비</strong>를 새로 구입·임차 시 중앙행정기관의 장의 사전 승인 및 협약 변경 필요</li>
  <li>취득가격 3천만원 이상(또는 공동활용 가능한 경우)의 연구시설·장비는 취득 후 <strong>30일 이내</strong>에 ZEUS 시스템에 등록하고 '국가연구시설장비정보등록증' 제출</li>
  <li>연구개발과제 종료일 <strong>2개월 전까지</strong> 구입·설치 또는 임차 완료(검수완료)</li>
  <li>통합 연구시설·장비비는 연구비 입금 후 <strong>90일 이내</strong>에 이체 처리</li>
</ol>

<h6>💰 중앙구매 기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>항목</th><th>금액</th></tr></thead>
  <tbody>
    <tr><td>연구시설 장비·기자재</td><td>단가 100만원(VAT 포함) 이상</td></tr>
    <tr><td>공사·용역·임차 등</td><td>건별 1,000만원(VAT 포함) 이상</td></tr>
  </tbody>
</table>

<h6>🏛️ 국가연구시설·장비 심의 체계</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>심의 범위</th></tr></thead>
  <tbody>
    <tr><td>국가연구시설장비심의위원회 (과기정통부)</td><td>국가연구개발사업 1억원 이상 연구시설·장비</td></tr>
    <tr><td>연구개발과제 평가단 (중앙행정기관)</td><td>국가연구개발사업 3천만원 이상 1억원 미만 (또는 1억원 이상 중 정부지원 1억원 미만)</td></tr>
    <tr><td>자체연구시설장비심의위원회 (주관기관)</td><td>국가연구개발사업(정출연기본사업) 3천만원 이상 1억원 미만 (또는 동일 조건)</td></tr>
  </tbody>
</table>
"""

_RESEARCH_MATERIALS_DESC = """
<h6>📌 사용용도</h6>
<ul>
  <li><strong>연구재료 구입비:</strong> 시약·재료 구입비 및 관련 부대비용</li>
  <li><strong>연구개발과제 관리비:</strong> 과제 수행을 위하여 필요한 관리시스템 등의 운영비</li>
  <li><strong>연구재료 제작비:</strong> 시험제품·시험설비 제작비용</li>
</ul>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>자산으로 등록하는 시험제품·시험설비는 <strong>자산 등록가(부대비용 포함)</strong>로 계상</li>
  <li>연구재료비는 연구개발과제 <strong>종료일까지</strong> 구매(검수완료)</li>
  <li>시험제품·시험설비를 자체 제작할 경우 참여연구자 이외의 인력에 대한 노무비 계상 가능</li>
  <li>연구개발과제 관리비는 해당 과제 수행을 위한 전산처리 및 관리비로 실소요 금액을 현금 계상. 기관 전체 전산처리·관리비는 계상 불가
    <br><small class="text-muted">※ 독립적으로 운영할 필요가 있는 홈페이지 구축·관리비, 온라인협력 플랫폼 운영비 등은 인정</small>
  </li>
</ol>

<h6>💰 중앙구매 기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>항목</th><th>금액</th></tr></thead>
  <tbody>
    <tr><td>시약 및 재료</td><td>견적금액 300만원(VAT 포함) 이상</td></tr>
    <tr><td>공사·용역·임차 등</td><td>건별 1,000만원(VAT 포함) 이상</td></tr>
  </tbody>
</table>
"""

_EXTERNAL_TECH_DESC = """
<h6>📌 사용용도</h6>
<p>기술도입비, 전문가활용비(자문료, 강사료, 회의수당, 원고료, 번역료), 연구개발서비스 활용비 등 외부 전문기술 활용을 위하여 필요한 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>기술도입비는 해당 기술을 도입하는데 실제 필요한 비용을 계상하며, 관련 증빙 자료를 첨부하여 실비 청구</li>
  <li>외부 전문기술 활용비를 <strong>직접비의 40% 범위</strong>에서 사용. 다만, 중앙행정기관의 장이 필요하다고 인정하는 경우 40% 초과 가능</li>
  <li>연구책임자나 참여연구자와 같은 연구실에 소속된 전임교원에게 전문가활용비 계상 불가</li>
  <li>관련 세법에 따라 각종 세금을 원천징수 후 해당자 계좌로 이체</li>
  <li>ERP시스템(전문가활용내역서)에 전문가 인적사항, 자문(강의)내용, 필요성을 입력하고 증빙자료 제출</li>
  <li>청탁금지법 적용 대상자의 외부강의 상한액 적용</li>
</ol>

<h6>💰 국내 전문가 지급기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>자문료(시간)</th><th>강사료(1회)</th><th>지급상한액</th></tr></thead>
  <tbody>
    <tr><td>가호 (전임교원·선임연구원 이상, 경력 10년↑)</td><td>200,000원 이하</td><td>1,000,000원 이하</td><td>1,500,000원</td></tr>
    <tr><td>나호 (가호 해당 외)</td><td>150,000원 이하</td><td>800,000원 이하</td><td>1,200,000원</td></tr>
  </tbody>
</table>

<h6>💰 국외 전문가 지급기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>자문료(단기/일)</th><th>자문료(장기/월)</th><th>강사료(1회)</th><th>지급상한액</th></tr></thead>
  <tbody>
    <tr><td>가호</td><td>$1,000 이하</td><td>$8,000 이하</td><td>$1,600 이하</td><td>$2,400 이하</td></tr>
    <tr><td>나호</td><td>$500 이하</td><td>$5,000 이하</td><td>$1,000 이하</td><td>$1,500 이하</td></tr>
  </tbody>
</table>

<h6>💰 원고료·번역료 지급기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>산정기준</th><th>지급기준</th></tr></thead>
  <tbody>
    <tr><td>원고료</td><td>A4 1장당 (200자 원고지 4매)</td><td>50,000원 이하</td></tr>
    <tr><td>원고료 (PPT)</td><td>슬라이드 2장 기준 (표지·목차·참고문헌 제외)</td><td>25,000원 이하</td></tr>
    <tr><td>번역료 (한→외)</td><td>A4 1장당</td><td>50,000원 이하</td></tr>
    <tr><td>번역료 (외→한)</td><td>A4 1장당</td><td>30,000원 이하</td></tr>
  </tbody>
</table>
"""

_MEETING_DESC = """
<h6>📌 사용용도</h6>
<p>회의장 임차료, 속기료, 통역료 또는 회의비 등 연구개발과제 수행을 위하여 필요한 회의·세미나 개최 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>회의 후 식대 비용은 <strong>1인당 50,000원 범위 내</strong>에서 계상 가능</li>
  <li>국가연구개발사업의 경우 사전에 내부결재(연구책임자 결재 필수)를 완료하고 외부참석자 포함 필수</li>
  <li>23시~6시 사이에 사용한 회의비 및 회의 후 후식 비용 처리 불가</li>
  <li>회의목적, 일시, 장소, 참여인원, 회의내용 등이 기재된 <strong>회의록 제출 필수</strong></li>
  <li>내·외부 참석자가 회의 참석 후 식사 불참 시 식비 사용 불가</li>
  <li>비대면(Zoom) 회의 후 내부 인원만 참여한 식비 사용 불가 (객관적 증빙 있는 경우 인정)</li>
  <li>학회·세미나개최비는 장소임대료, 행사경비, 자료집 발간비, 참석자 식사비, 음료·다과비 등 포함. 사전에 개최 계획(예산내역 포함) 수립 필요</li>
</ol>

<h6>💰 통역료·속기료 지급기준</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>지급기준</th><th>비고</th></tr></thead>
  <tbody>
    <tr><td>수행 통역</td><td>100,000원</td><td rowspan="2">1인당 1일 1시간 기준 (초과 시간당 10만원 가산)</td></tr>
    <tr><td>국제회의 통역</td><td>100,000원</td></tr>
    <tr><td>속기 기본료</td><td>300,000원/1시간</td><td rowspan="5">1급 속기사 기준, (사)대한속기협회 고시요금 적용</td></tr>
    <tr><td>녹음재생</td><td>350,000원/1시간</td></tr>
    <tr><td>전문분야</td><td>350,000원/1시간</td></tr>
    <tr><td>외국어속기</td><td>400,000원/1시간</td></tr>
    <tr><td>요점속기</td><td>200,000원/1시간</td></tr>
  </tbody>
</table>
"""

_TRIP_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행을 위한 국내·외 출장 비용 (파견·전보·주거 관련 지원 비용 포함)</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>여비는 출장자 개인 명의 통장으로 이체하며, 교통비·숙박비는 <strong>연구비 카드 사용이 원칙</strong></li>
</ol>

<h6>🚆 국내 출장</h6>
<ul>
  <li>여비는 공무원 여비규정 적용 (캠퍼스 간 출장: 부산대학교 캠퍼스 간 출장여비 지급기준 적용)</li>
  <li>연구책임자 및 참여연구자는 사전에 소속기관의 출장 승인 필요. 학생연구자는 ERP 시스템 출장신청서 이용</li>
  <li>개인카드 사용 시 실제 숙박·교통비 증빙자료 및 운임·숙박비 확인서 제출</li>
  <li>출장지 관계기관에서 식대·식사를 제공하는 경우 해당 금액 차감 후 신청</li>
</ul>

<h6>✈️ 국외 출장</h6>
<ul>
  <li>여비는 공무원 여비규정 적용</li>
  <li>사전에 <strong>공무국외출장계획서</strong> 및 출장관련 증빙(학회·강좌·워크숍 프로그램 등) 제출하여 출장허가 필요</li>
  <li>개인카드 사용 시 실제 숙박·교통비 증빙자료 및 운임·숙박비 확인서 제출</li>
  <li>귀국 후 <strong>국외출장결과보고서</strong> 작성·제출</li>
  <li>국외여비 정산 시 기내 숙식비 제외</li>
</ul>
"""

_SOFTWARE_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행을 위한 소프트웨어의 구입·설치·임차·사용대차 비용 또는 데이터베이스·네트워크 이용료</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>국가연구개발사업의 경우 <strong>연구개발과제(단계) 종료일 2개월 전까지</strong> 사용계약 체결</li>
  <li>소프트웨어 사용계약 기간이 연구개발 기간을 초과하더라도 사용계약 기간이 최소단위임을 소명하는 경우 계약금액 전액 계상 가능</li>
  <li>연구실운영비의 사무용 기기 및 사무용 소프트웨어의 구입·설치·임차 비용은 제외</li>
  <li>구입 및 자산관리는 「부산대학교 연구물품 등의 중앙구매에 관한 기준」에 따라 운영</li>
</ol>
"""

_CLOUD_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행을 위한 클라우드컴퓨팅서비스 이용료</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>「클라우드컴퓨팅 발전 및 이용자 보호에 관한 법률 시행령」 제8조의2 제3항에 따라 구축·운영되는 이용지원시스템(<a href="https://www.digitalmarket.kr" target="_blank">www.digitalmarket.kr</a>)을 확인한 후 필요한 경비 계상</li>
  <li>정액제를 사용하는 경우에는 소프트웨어 활용비 계상(집행)기준에 따라 운영</li>
</ol>
"""

_LAB_OP_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행을 위하여 필요한 사무용 기기·소프트웨어 구입·설치·임차 비용, 사무용품비, 연구실 운영 소모성 비용, 냉난방·환경유지 기기·비품 구입·유지 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>연구수행을 위해 연구실에 비치·이용할 경우 집행 가능. 연구수행과 무관한 개인성 경비는 집행 불가</li>
  <li>연구실 환경 유지 기기·비품 구입 시 연구과제 관련성 및 과도한 연구비 사용 여부 검토 후 구입</li>
  <li>세부 구매절차·검수·자산관리는 「부산대학교 연구물품 등의 중앙구매에 관한 기준」에 따라 운영</li>
</ol>

<h6>❌ 불인정 항목</h6>
<table class="table table-sm table-bordered small">
  <thead class="table-light"><tr><th>구분</th><th>항목(예시)</th></tr></thead>
  <tbody>
    <tr><td>연구·연구실 환경유지와 직접 관련성 적은 비품</td><td>TV, 비디오, 라디오, 음향시설, 운동기구, 카페트, 커피머신 등</td></tr>
    <tr><td>시설유지·수선 비용</td><td>건물보수, 페인트칠, 배관공사, 중앙집중식 냉난방·공조시설, 생수기 미설치 생수 등</td></tr>
    <tr><td>연구과제와 무관한 소모성 비용</td><td>주류 등 유흥성 비용, 인건비성 비용, 별도 수당, 과태료·벌금, 취소수수료, 커피·음료·다과, 개인 기호품 등</td></tr>
  </tbody>
</table>
"""

_RESEARCH_PERSONNEL_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행과 직접 관련된 교육·훈련 비용, 학회·세미나 참가비, 야근(특근) 식대</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>연구과제에 <strong>참여하고 있는 연구자에게만</strong> 지급 가능</li>
  <li>교육훈련비는 연구과제와 직접 관련된 교육훈련경비로 교육훈련수료증 사본 등 증빙자료 제출</li>
  <li>연구개발과제 관련 학회의 연회비(1년)는 대상기간이 연구개발 기간을 포함한 전·후 기간에 대해서도 인정 (사용일은 연구개발 기간 내 포함되어야 함)</li>
  <li>야근(특근)식대는 <strong>1인당 10,000원 이하</strong> 계상 가능 (평일 점심 식대는 집행 불가)</li>
  <li>연구원 식대 청구 시 시간외근무 확인대장 활용</li>
  <li>야근·특근 식대는 <strong>금정구, 동래구, 양산시, 밀양시 관내</strong>에서만 사용 가능</li>
</ol>
"""

_OVERSEAS_RESEARCHER_DESC = """
<h6>📌 사용용도</h6>
<p>외국에 소재한 정부·기관·단체 소속 연구자 등 전문성을 갖춘 해외 연구자에게 지급되는 장려금, 체재비 등 국내 유치에 필요한 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>아래 요건을 갖추어 <strong>지원기관의 장의 인정</strong>을 받은 경우에만 계상 가능</li>
</ol>
<ul>
  <li>지원대상자가 전체 연구개발과제 기간 중 <strong>6개월 이상</strong> 국내 거주하며 과제 참여</li>
  <li>지원대상자가 연구책임자 또는 연구개발기관의 장과 <strong>6촌 이내 혈족 또는 4촌 이내 인척 관계에 있지 않아야</strong> 함</li>
  <li>본교 및 연구관리기관의 임용 기준에 따라 해외연구자 유치 절차 진행</li>
</ul>
<ol start="2">
  <li>원래 계획보다 증액하여 사용하려는 경우 지원기관의 장의 <strong>사전 승인</strong> 필요</li>
</ol>
"""

_COMPREHENSIVE_MGMT_DESC = """
<h6>📌 사용용도</h6>
<p>연구인프라 조성을 목적으로 하는 사업의 목표 달성을 위한 기획·조정 또는 추진과정에 대한 자문이나 관리 비용</p>

<h6>📋 계상(집행)기준</h6>
<p>자문료는 외부전문기술활동비 지급기준(표 5~10)을 기준으로 계상하며, 그 외 경비는 실 소요 경비 계상</p>
"""

_OTHER_EXPENSES_DESC = """
<h6>📌 사용용도</h6>
<p>문헌구입비, 논문게재료, 인쇄·복사·인화비, 슬라이드 제작비, 각종 세금·공과금, 우편요금, 택배비, 수수료, 공공요금, 일용직 활용비 등 연구개발과제와 직접 관련 있는 그 밖의 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>연구과제와 직접 관련 있는 도서·문헌에 한하여 구입 가능하며, 구입 도서는 ERP시스템에 등록</li>
  <li>우편요금, 택배비, 퀵서비스 이용료, 전화·전용회선 사용료, 제세공과금 등 실소요 경비 계상</li>
  <li>인쇄·복사·인화·슬라이드 제작비, 공고료, 계약용 수입 인지대, 논문게재료, 보증보험료, 수수료(환전·통관·신문공고·위탁정산·환차손 등), 각종 세금 실소요 경비 계상</li>
  <li>일시적 비참여 연구원에게는 일용직 활용비로 처리하며 계약서 작성 (인적사항·활용내용·필요성 명시)</li>
  <li><strong>납부기한 이후 발생한 연체료는 불인정</strong></li>
</ol>
"""

_RESEARCH_ALLOWANCE_DESC = """
<h6>📌 사용용도</h6>
<p>연구개발과제 수행에 참여하는 연구책임자 및 연구자(학생연구자 포함)에게 지급하는 장려금</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>인건비(현물·미지급·학생인건비 포함)의 <strong>20% 범위 내</strong>에서 계상. 승인된 계획보다 증액 편성 불가</li>
  <li>직접비 사용 비율이 <strong>80% 이상</strong>인 경우 계상금액 100% 지급 가능. 참여연구자가 복수인 경우 1명이 받을 수 있는 금액은 70%까지</li>
  <li>연구개발과제 시작 시점에 계상한 금액보다 증액 계상 불가하며, <strong>사용 잔액은 다음 단계 이월 불가</strong></li>
  <li>연구근접지원인력에게 연구수당 지급 불가</li>
  <li>지급대상은 당초 계획서에 포함되거나 계획 변경 후 과제에 참여하고 있는 연구책임자·모든 참여연구자</li>
  <li>ERP시스템 및 연구수당 신청서를 활용하여 연구과제 기여도를 평가하고, 평가점수에 따라 지급</li>
  <li>전체 평가대상자의 평가점수 합은 <strong>100점</strong>이어야 함</li>
  <li>임금과 같이 통상적으로 지급 불가</li>
</ol>
"""

DESCRIPTIONS = {
    'equipment_consumables':      _EQUIPMENT_DESC,
    'equipment_service':          _EQUIPMENT_DESC,
    'central_purchase_equipment': _EQUIPMENT_DESC,
    'central_purchase_reagent':   _RESEARCH_MATERIALS_DESC,
    'central_purchase_service':   _EQUIPMENT_DESC,
    'ip_creation': """
<h6>📌 사용용도</h6>
<p>기술·특허·표준 정보 조사·분석, 원천·핵심특허 확보전략 수립 등 지식재산 창출 활동에 필요한 비용</p>

<h6>📋 계상(집행)기준</h6>
<ol>
  <li>연구개발과제의 기획·전략 수립 등 연구개발과제의 수행 초기단계에서 지식재산 창출을 위해 필요한 비용</li>
  <li>지식재산권의 출원·등록·유지에 필요한 비용(간접비 중 성과활용지원비)은 <strong>계상 불가</strong></li>
</ol>
""",
    'tech_introduction':  _EXTERNAL_TECH_DESC,
    'expert_utilization': _EXTERNAL_TECH_DESC,
    'rd_service':         _EXTERNAL_TECH_DESC,
    'meeting_fee':          _MEETING_DESC,
    'seminar_fee':          _MEETING_DESC,
    'domestic_trip':        _TRIP_DESC,
    'overseas_trip':        _TRIP_DESC,
    'software':             _SOFTWARE_DESC,
    'cloud':                _CLOUD_DESC,
    'lab_operation':        _LAB_OP_DESC,
    'education_training':   _RESEARCH_PERSONNEL_DESC,
    'conference_fee':       _RESEARCH_PERSONNEL_DESC,
    'overtime_meal':        _RESEARCH_PERSONNEL_DESC,
    'overseas_researcher':  _OVERSEAS_RESEARCHER_DESC,
    'comprehensive_mgmt':   _COMPREHENSIVE_MGMT_DESC,
    'other_expenses':       _OTHER_EXPENSES_DESC,
    'research_allowance':   _RESEARCH_ALLOWANCE_DESC,
}


def get_categories():
    """카테고리별로 그룹핑"""
    categories = {}
    for key, info in EXPENSE_TYPES.items():
        cat = info['category']
        if cat not in categories:
            categories[cat] = {'icon': info['category_icon'], 'types': {}}
        categories[cat]['types'][key] = info
    return categories


def image_to_pdf_bytes(file):
    img = Image.open(file)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='PDF', resolution=150)
    buf.seek(0)
    return buf


def merge_files(files_dict, doc_order):
    writer = PdfWriter()
    for doc_id in doc_order:
        for f in files_dict.get(doc_id, []):
            f.seek(0)
            name = f.filename.lower()
            if name.endswith('.pdf'):
                reader = PdfReader(f)
                for page in reader.pages:
                    writer.add_page(page)
            elif name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                pdf_buf = image_to_pdf_bytes(f)
                reader = PdfReader(pdf_buf)
                for page in reader.pages:
                    writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


@app.route('/')
def index():
    return render_template('index.html', categories=get_categories(), descriptions=DESCRIPTIONS)


@app.route('/merge', methods=['POST'])
def merge():
    expense_type = request.form.get('expense_type')

    if not expense_type or expense_type not in EXPENSE_TYPES:
        return jsonify({'error': '유효하지 않은 비용 유형입니다.'}), 400

    info      = EXPENSE_TYPES[expense_type]
    doc_order = [d['id'] for d in info['documents']]
    files_dict = {}

    for doc in info['documents']:
        uploaded = [f for f in request.files.getlist(doc['id']) if f.filename]
        if doc['required'] and not uploaded:
            return jsonify({'error': f"'{doc['name']}' 파일이 필요합니다."}), 400
        if uploaded:
            files_dict[doc['id']] = uploaded

    if not files_dict:
        return jsonify({'error': '파일을 하나 이상 업로드해주세요.'}), 400

    try:
        merged   = merge_files(files_dict, doc_order)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{info['name']}_{date_str}.pdf"
        return send_file(merged, mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': f'PDF 병합 오류: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
