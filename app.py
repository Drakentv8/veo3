from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import openai
import io
import time
from datetime import datetime
import re
import os
from werkzeug.utils import secure_filename
import time as _time

UPLOAD_FOLDER = 'static/brand_logos'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'  # diperlukan untuk session

# Konfigurasi NVIDIA API
openai.api_key = "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"
openai.api_base = "https://integrate.api.nvidia.com/v1"

# Data untuk dropdown
NICHES = [
    {'value': 'fashion', 'label': '👗 Fashion'},
    {'value': 'food', 'label': '🍔 Makanan'},
    {'value': 'gadget', 'label': '📱 Gadget'},
    {'value': 'cosmetic', 'label': '💄 Kosmetik'},
    {'value': 'furniture', 'label': '🪑 Furniture'},
    {'value': 'health', 'label': '💊 Kesehatan'},
    {'value': 'education', 'label': '📚 Pendidikan'},
    {'value': 'sport', 'label': '⚽ Olahraga'}
]

TONES = [
    {'value': 'funny', 'label': '😂 Lucu'},
    {'value': 'luxury', 'label': '💎 Mewah'},
    {'value': 'educational', 'label': '🎓 Edukatif'},
    {'value': 'dramatic', 'label': '🎭 Dramatis'},
    {'value': 'inspirational', 'label': '✨ Inspiratif'}
]

DURATIONS = ['8 detik', '15 detik', '30 detik', '60 detik']
ASPECT_RATIOS = ['1:1 (Square)', '9:16 (Vertical)', '16:9 (Horizontal)']
LANGUAGES = ['Indonesia', 'English', 'Jawa', 'Sunda']

def generate_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="nvidia/llama-3.3-nemotron-super-49b-v1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
                top_p=0.9
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)

def clean_formatting(text, is_caption=False):
    # Hilangkan heading markdown (###, ####, ##, #)
    text = re.sub(r"#+ ", '', text)
    text = re.sub(r"#+", '', text)
    # Hilangkan garis tabel markdown dan karakter pipe
    text = re.sub(r"\|", '', text)
    text = re.sub(r"---+", '', text)
    # Hilangkan spasi berlebih di awal/akhir baris
    text = '\n'.join(line.strip() for line in text.split('\n'))
    # Hilangkan baris kosong berlebih
    text = re.sub(r"(\n\s*){2,}", '\n\n', text)
    # Untuk caption, pisahkan hashtag ke baris baru jika memungkinkan
    if is_caption:
        # Pisahkan baris hashtag jika ada kata 'Hashtag:'
        if 'Hashtag:' in text:
            parts = text.split('Hashtag:')
            caption = parts[0].strip()
            hashtags_raw = parts[1].strip()
            # Ambil semua kata yang diawali #
            hashtags = re.findall(r'#\w+', hashtags_raw)
            # Jika tidak ada #, ambil semua kata dan tambahkan #
            if not hashtags:
                # Ambil semua kata (tanpa spasi, tanpa karakter non-alfanumerik)
                words = re.findall(r'\w+', hashtags_raw)
                hashtags = [f'#{w}' for w in words if w]
            text = caption + '\nHashtag:\n' + ' '.join(hashtags)
        elif text.count('#') > 2:
            # Pisahkan baris pertama (caption) dan sisanya hashtag
            lines = text.split('\n')
            caption_line = lines[0]
            hashtags = []
            for line in lines[1:]:
                if '#' in line:
                    hashtags += re.findall(r'#\w+', line)
            if hashtags:
                text = caption_line + '\nHashtag:\n' + ' '.join(hashtags)
        else:
            # Deteksi baris yang kemungkinan besar adalah hashtag tanpa #
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if (i > 0 and len(line.split()) >= 5 and not any('#' in w for w in line.split())):
                    # Anggap ini baris hashtag tanpa #
                    words = re.findall(r'\w+', line)
                    hashtags = [f'#{w}' for w in words if w]
                    lines[i] = ' '.join(hashtags)
                    text = '\n'.join(lines)
                    break
    # Hilangkan asterisks
    text = text.replace('*', '')
    return text

def generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name=None):
    # Sisipkan brand_name jika ada
    brand_str = f" ({brand_name})" if brand_name else ""
    # Generate VEO Prompt
    veo_prompt = f"""Buatkan prompt video penjualan profesional untuk produk {nama_produk}{brand_str} dalam niche {niche['label']}. 
    - Tone: {tone['label']}
    - Durasi: {durasi}
    - Aspect Ratio: {aspect_ratio}
    - Bahasa: {language}
    - Sertakan: Visual produk, suasana, emosi, target audiens, angle kamera, lighting, dan gerakan kamera"""
    
    try:
        t0 = _time.time()
        veo_result = generate_with_retry(veo_prompt)
        print(f"[LOG] Waktu generate VEO Prompt: {round(_time.time()-t0,2)} detik")
        veo_result = clean_formatting(veo_result)
    except:
        veo_result = f"Visualisasikan {nama_produk}{brand_str} di setting {niche['label'].lower()}, dengan tone {tone['label'].lower()}. Tampilkan produk dari berbagai angle dengan lighting profesional. Sertakan close-up fitur utama dan happy customer menggunakan produk."

    # Generate Narration
    narration_prompt = f"""Buatkan narasi video penjualan untuk {nama_produk}{brand_str} dengan:
    - Niche: {niche['label']}
    - Tone: {tone['label']}
    - Durasi: {durasi}
    - Bahasa: {language}
    Narasi harus persuasif, jelas, dan sesuai durasi."""
    
    try:
        t0 = _time.time()
        narration = generate_with_retry(narration_prompt)
        print(f"[LOG] Waktu generate Narasi: {round(_time.time()-t0,2)} detik")
        narration = clean_formatting(narration)
    except:
        narration = f"Perkenalkan {nama_produk}{brand_str} - solusi terbaik untuk kebutuhan {niche['label'].lower()} Anda! Dapatkan sekarang!"

    # Generate Caption & Hashtags
    caption_prompt = f"""Buatkan caption Instagram/TikTok untuk promosi {nama_produk}{brand_str}:
    - Niche: {niche['label']}
    - Tone: {tone['label']}
    - Bahasa: {language}
    Sertakan emoji dan 10 hashtag relevan"""
    
    try:
        t0 = _time.time()
        caption_result = generate_with_retry(caption_prompt)
        print(f"[LOG] Waktu generate Caption: {round(_time.time()-t0,2)} detik")
        caption_result = clean_formatting(caption_result, is_caption=True)
    except:
        base_hashtags = {
            'fashion': '#fashion #style #ootd #trend #modis',
            'food': '#kuliner #makanan #foodie #enak #recommended',
            'gadget': '#teknologi #gadget #tech #innovation #smart',
            'cosmetic': '#beauty #skincare #makeup #glowing #cantik',
            'furniture': '#rumah #interior #desain #dekorasi #furniture'
        }
        caption = f"{nama_produk}{brand_str} - solusi terbaik untuk Anda! ✨"
        hashtags = base_hashtags.get(niche['value'], '#viral #trending #fyp #recommended #produklokal')
        caption_result = f"{caption}\n\n{hashtags}"

    # Generate Call-to-Action
    cta_prompt = f"""Buatkan 3 pilihan call-to-action untuk video promosi {nama_produk}{brand_str}:
    - Tone: {tone['label']}
    - Bahasa: {language}
    Format: 1. [CTA pendek], 2. [CTA menengah], 3. [CTA panjang]"""
    
    try:
        t0 = _time.time()
        cta = generate_with_retry(cta_prompt)
        print(f"[LOG] Waktu generate CTA: {round(_time.time()-t0,2)} detik")
        cta = clean_formatting(cta)
    except:
        cta = "1. Beli sekarang!\n2. Kunjungi link di bio untuk info lebih lanjut!\n3. Jangan lewatkan promo spesial ini, pesan sekarang sebelum kehabisan!"

    return {
        'veo_prompt': veo_result,
        'narration': narration,
        'caption': caption_result,
        'cta': cta,
        'generated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama_produk = request.form['nama_produk']
        niche = next((item for item in NICHES if item['value'] == request.form['niche']), NICHES[0])
        tone = next((item for item in TONES if item['value'] == request.form['tone']), TONES[0])
        durasi = request.form['durasi']
        aspect_ratio = request.form['aspect_ratio']
        language = request.form['language']
        
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language)
        
        return render_template('index.html', 
                             niches=NICHES,
                             tones=TONES,
                             durations=DURATIONS,
                             aspect_ratios=ASPECT_RATIOS,
                             languages=LANGUAGES,
                             result=result,
                             form_data=request.form)
    
    return render_template('index.html',
                         niches=NICHES,
                         tones=TONES,
                         durations=DURATIONS,
                         aspect_ratios=ASPECT_RATIOS,
                         languages=LANGUAGES)

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    content = f"""AI PROMPTER PRO - HASIL GENERATOR PROMO VIDEO
Tanggal: {data['generated_at']}
Produk: {data['nama_produk']}

=== PROMPT VEO 3 ===
{data['veo_prompt']}

=== NARASI VIDEO ===
{data['narration']}

=== CAPTION SOSMED ===
{data['caption']}

=== CALL-TO-ACTION ===
{data['cta']}

=== INFORMASI PROYEK ===
Niche: {data['niche_label']}
Tone: {data['tone_label']}
Durasi: {data['durasi']}
Aspect Ratio: {data['aspect_ratio']}
Bahasa: {data['language']}
"""

    mem = io.BytesIO()
    mem.write(content.encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        as_attachment=True,
        download_name=f"AI_Prompter_Pro_{data['nama_produk'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
        mimetype='text/plain'
    )

@app.route('/generate', methods=['POST'])
def generate():
    try:
        nama_produk = request.form.get('nama_produk')
        brand_name = request.form.get('brand_name')
        brand_logo = request.files.get('brand_logo')
        niche_value = request.form.get('niche')
        tone_value = request.form.get('tone')
        durasi = request.form.get('durasi')
        aspect_ratio = request.form.get('aspect_ratio')
        language = request.form.get('language')

        # Simpan logo jika ada
        logo_url = None
        if brand_logo and brand_logo.filename:
            filename = secure_filename(brand_logo.filename)
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            brand_logo.save(logo_path)
            logo_url = url_for('static', filename=f'brand_logos/{filename}')

        niche = next((item for item in NICHES if item['value'] == niche_value), NICHES[0])
        tone = next((item for item in TONES if item['value'] == tone_value), TONES[0])

        # Progressive step simulation
        steps = ['veo', 'narration', 'caption', 'cta']
        result = {}
        for idx, step in enumerate(steps):
            if step == 'veo':
                result['veo_prompt'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['veo_prompt']
            elif step == 'narration':
                result['narration'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['narration']
            elif step == 'caption':
                result['caption'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['caption']
            elif step == 'cta':
                result['cta'] = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['cta']
        result['generated_at'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        result['brand_name'] = brand_name
        result['brand_logo'] = logo_url
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate_step', methods=['POST'])
def generate_step():
    step = request.form.get('step')
    # Data form hanya dikirim sekali di awal, lalu disimpan di session
    if step == 'init':
        session['generate_data'] = {
            'nama_produk': request.form.get('nama_produk'),
            'brand_name': request.form.get('brand_name'),
            'brand_logo': None,
            'niche_value': request.form.get('niche'),
            'tone_value': request.form.get('tone'),
            'durasi': request.form.get('durasi'),
            'aspect_ratio': request.form.get('aspect_ratio'),
            'language': request.form.get('language'),
            'brand_logo_filename': None
        }
        brand_logo = request.files.get('brand_logo')
        if brand_logo and brand_logo.filename:
            filename = secure_filename(brand_logo.filename)
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            brand_logo.save(logo_path)
            session['generate_data']['brand_logo'] = url_for('static', filename=f'brand_logos/{filename}')
            session['generate_data']['brand_logo_filename'] = filename
        session['generate_status'] = {}
        return jsonify({'success': True})

    # Step berikutnya: generate per step
    data = session.get('generate_data', {})
    status = session.get('generate_status', {})
    nama_produk = data.get('nama_produk')
    brand_name = data.get('brand_name')
    brand_logo = data.get('brand_logo')
    niche_value = data.get('niche_value')
    tone_value = data.get('tone_value')
    durasi = data.get('durasi')
    aspect_ratio = data.get('aspect_ratio')
    language = data.get('language')
    niche = next((item for item in NICHES if item['value'] == niche_value), NICHES[0])
    tone = next((item for item in TONES if item['value'] == tone_value), TONES[0])

    t0 = _time.time()
    result = None
    if step == 'veo':
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['veo_prompt']
        status['veo'] = {'result': result, 'elapsed': round(_time.time()-t0,2)}
    elif step == 'narration':
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['narration']
        status['narration'] = {'result': result, 'elapsed': round(_time.time()-t0,2)}
    elif step == 'caption':
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['caption']
        status['caption'] = {'result': result, 'elapsed': round(_time.time()-t0,2)}
    elif step == 'cta':
        result = generate_content(nama_produk, niche, tone, durasi, aspect_ratio, language, brand_name)['cta']
        status['cta'] = {'result': result, 'elapsed': round(_time.time()-t0,2)}
        # Final step, tambahkan info lain
        status['generated_at'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        status['brand_name'] = brand_name
        status['brand_logo'] = brand_logo
    session['generate_status'] = status
    return jsonify({'success': True, 'step': step, 'result': result, 'elapsed': status[step]['elapsed'] if step in status else 0, 'all_status': status})

if __name__ == '__main__':
    app.run(debug=True)