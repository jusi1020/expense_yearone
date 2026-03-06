from flask import Flask, render_template, request, send_file, jsonify
from pypdf import PdfWriter, PdfReader
from PIL import Image
from datetime import datetime
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# ─── 비용 유형 정의 (여기에 추가하면 자동으로 UI에 반영) ───────────────────
EXPENSE_TYPES = {
    'domestic_trip': {
        'name': '국내 출장',
        'icon': '🚆',
        'documents': [
            {'id': 'application',    'name': '출장신청서',    'required': True,  'accept': '.pdf'},
            {'id': 'transport',      'name': '교통비 영수증', 'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'accommodation',  'name': '숙박비 영수증', 'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'proof',          'name': '출장 증빙사진', 'required': False, 'accept': '.jpg,.jpeg,.png,.pdf'},
        ]
    },
    'overseas_trip': {
        'name': '국외 출장',
        'icon': '✈️',
        'documents': [
            {'id': 'application',    'name': '출장신청서',    'required': True,  'accept': '.pdf'},
            {'id': 'flight',         'name': '항공권',        'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'accommodation',  'name': '숙박비 영수증', 'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'passport',       'name': '여권 사본',     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'proof',          'name': '출장 증빙사진', 'required': False, 'accept': '.jpg,.jpeg,.png,.pdf'},
        ]
    },
    'research_materials': {
        'name': '연구 재료 구매',
        'icon': '🔬',
        'documents': [
            {'id': 'application', 'name': '구매신청서', 'required': True,  'accept': '.pdf'},
            {'id': 'quote',       'name': '견적서',     'required': False, 'accept': '.pdf,.jpg,.jpeg,.png'},
            {'id': 'receipt',     'name': '영수증',     'required': True,  'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
    'office_supplies': {
        'name': '사무용품 구매',
        'icon': '📎',
        'documents': [
            {'id': 'application', 'name': '구매신청서', 'required': True, 'accept': '.pdf'},
            {'id': 'receipt',     'name': '영수증',     'required': True, 'accept': '.pdf,.jpg,.jpeg,.png'},
        ]
    },
}
# ───────────────────────────────────────────────────────────────────────────────


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
    return render_template('index.html', expense_types=EXPENSE_TYPES)


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
        merged = merge_files(files_dict, doc_order)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{info['name']}_{date_str}.pdf"
        return send_file(merged, mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': f'PDF 병합 오류: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
