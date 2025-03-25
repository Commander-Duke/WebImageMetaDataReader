import os
import exifread
from flask import Flask, request, render_template_string, send_file, redirect, url_for
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>MetaViewer Web</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        h1 { color: #333; }
        textarea { width: 100%; height: 400px; }
        .file-section { margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>🧠 MetaViewer Web – Bild-Metadaten-Explorer</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <div class="file-section">
            <label for="files">Mehrere Dateien auswählen:</label><br>
            <input type="file" name="files" multiple required>
        </div>
        <button type="submit">Metadaten auslesen</button>
    </form>
    {% if results %}
        {% for filename, data in results.items() %}
            <h2>📁 {{ filename }}</h2>
            <pre>{{ data }}</pre>
        {% endfor %}
        <a href="{{ url_for('download_export') }}">💾 Exportiere alle Metadaten (.zip)</a>
    {% endif %}
</body>
</html>
"""

def extract_all_metadata(file_path):
    parser = createParser(file_path)
    if not parser:
        return "❌ Datei konnte nicht geparst werden."
    with parser:
        metadata = extractMetadata(parser)
        if not metadata:
            return "❌ Keine Metadaten gefunden."
        return "\n".join(metadata.exportPlaintext())

def get_decimal_from_dms(dms, ref):
    degrees = dms[0].num / dms[0].den
    minutes = dms[1].num / dms[1].den
    seconds = dms[2].num / dms[2].den
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def extract_gps_data(file_path):
    gps_lines = []
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lat_ref = tags.get("GPS GPSLatitudeRef")
        gps_lon = tags.get("GPS GPSLongitude")
        gps_lon_ref = tags.get("GPS GPSLongitudeRef")

        if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
            lat = get_decimal_from_dms(gps_lat.values, gps_lat_ref.values)
            lon = get_decimal_from_dms(gps_lon.values, gps_lon_ref.values)
            gps_lines.append("\n🧭 GPS-Koordinaten:")
            gps_lines.append(f"Latitude: {lat}")
            gps_lines.append(f"Longitude: {lon}")
            gps_lines.append(f"🌍 Google Maps: https://maps.google.com/?q={lat},{lon}")
        else:
            gps_lines.append("\nℹ️ Keine GPS-Daten gefunden.")
    except Exception as e:
        gps_lines.append(f"⚠️ Fehler beim Auslesen der GPS-Daten: {str(e)}")
    return "\n".join(gps_lines)

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    results = {}
    export_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'export')
    os.makedirs(export_dir, exist_ok=True)

    for file in files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        metadata = extract_all_metadata(file_path)
        gps = extract_gps_data(file_path)
        combined = f"{metadata}\n{gps}"
        results[filename] = combined

        # Speichere für Export
        with open(os.path.join(export_dir, filename + '_metadata.txt'), 'w', encoding='utf-8') as f:
            f.write(combined)

    return render_template_string(HTML_TEMPLATE, results=results)

@app.route('/download')
def download_export():
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], 'all_metadata.zip')
    export_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'export')
    with ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(export_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=file)
    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
