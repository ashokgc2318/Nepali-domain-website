from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import numpy as np
import io
import os

app = Flask(__name__)

def parse_ntc_timestamp(val):
    """Converts 14-digit NTC raw timestamp string (YYYYMMDDHHMMSS) to formatted string."""
    s = str(val).split('.')[0].strip()
    if len(s) == 14 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s}:{s}:{s}"
    return str(val)

def clean_cell_id(val):
    """Normalizes NTC and NCELL Cell IDs for seamless VLOOKUP matching."""
    if pd.isna(val):
        return ""
    val_str = str(val).strip().upper()
    if 'E+' in val_str or 'E-' in val_str:
        try:
            val_str = str(int(float(val_str)))
        except ValueError:
            pass
    elif val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_cdr():
    carrier = request.form.get('carrier')
    cdr_file = request.files.get('cdr_file')
    tower_file = request.files.get('tower_file')

    if not cdr_file:
        return jsonify({'error': 'No CDR file provided'}), 400

    # Read CDR Raw File
    if cdr_file.filename.endswith('.xls'):
        raw_df = pd.read_excel(cdr_file, engine='xlrd')
    else:
        raw_df = pd.read_excel(cdr_file)

    # Read Tower Database if provided
    tower_df = None
    if tower_file:
        if tower_file.filename.endswith('.xls'):
            tower_df = pd.read_excel(tower_file, engine='xlrd')
        else:
            tower_df = pd.read_excel(tower_file)

    processed_records = []
    top_contacts = []
    imei_list = []

    if carrier == 'NTC':
        # 1. Processing NTC CDR Structure
        df = raw_df.copy()
        df['Date_Time'] = df['DEST_SESSION_START_TIME'].apply(parse_ntc_timestamp)
        df['Call_Type_Label'] = df['DEST_CALL_TYPE'].map({0: 'Out', 1: 'In'}).fillna(df['DEST_CALL_TYPE'])
        df['Cell_Clean'] = df['DEST_CELL_ID'].apply(clean_cell_id)

        # Tower Location VLOOKUP
        df['Location_Name'] = 'Unknown Location'
        if tower_df is not None:
            # Assuming column 'Unnamed: 4' or 'Cell ID' holds tower lookup keys
            tower_key_col = 'Unnamed: 4' if 'Unnamed: 4' in tower_df.columns else tower_df.columns[0]
            name_col = 'Cell Name' if 'Cell Name' in tower_df.columns else tower_df.columns[1]
            tower_df['Cell_Clean'] = tower_df[tower_key_col].apply(clean_cell_id)
            
            merged = df.merge(tower_df[['Cell_Clean', name_col]], on='Cell_Clean', how='left')
            df['Location_Name'] = merged[name_col].fillna('Unknown Location')

        # Filter and retain specified key columns
        processed_df = pd.DataFrame({
            'User Number': df.get('DEST_USER_NUMBER', ''),
            'Opposite Number': df.get('DEST_OPP_NUMBER', ''),
            'Date & Time': df['Date_Time'],
            'Call Type': df['Call_Type_Label'],
            'Duration (s)': df.get('DEST_DURATION', 0),
            'Cell ID': df.get('DEST_CELL_ID', ''),
            'Location': df['Location_Name'],
            'IMEI': df.get('DEST_IMEI', '').astype(str).str.replace('.0', '', regex=False)
        })

        # Extract IMEIs from Outgoing Calls
        outgoing_imeis = processed_df[processed_df['Call Type'] == 'Out']['IMEI'].unique()
        imei_list = [str(x) for x in outgoing_imeis if str(x).lower() not in ['nan', 'none', '']]

    else:
        # 2. Processing NCELL CDR Structure
        df = raw_df.copy()
        df['Cell_Clean'] = df['Location'].apply(clean_cell_id)
        df['Location_Name'] = 'Unknown Location'

        if tower_df is not None:
            tower_key_col = 'Cell ID' if 'Cell ID' in tower_df.columns else tower_df.columns[0]
            name_col = 'Location' if 'Location' in tower_df.columns else tower_df.columns[1]
            tower_df['Cell_Clean'] = tower_df[tower_key_col].apply(clean_cell_id)
            
            merged = df.merge(tower_df[['Cell_Clean', name_col]], on='Cell_Clean', how='left')
            df['Location_Name'] = merged[name_col].fillna('Unknown Location')

        processed_df = pd.DataFrame({
            'User Number': df.get('Service Number', ''),
            'Opposite Number': df.get('Target Party B Mobile No', ''),
            'Date & Time': df.get('Start Time', ''),
            'Call Type': df.get('In/Out', ''),
            'Usage / Duration': df.get('Usage', 0),
            'Cell ID': df['Cell_Clean'],
            'Location': df['Location_Name'],
            'Service Type': df.get('Service Type Name', '')
        })

    # Frequency analysis (excluding system/internet logs)
    voice_contacts = processed_df[~processed_df['Opposite Number'].astype(str).str.lower().isin(['internet', 'nan', 'none'])]
    freq_df = voice_contacts['Opposite Number'].value_counts().head(10).reset_index()
    freq_df.columns = ['Opposite Number', 'Call Count']
    top_contacts = freq_df.to_dict(orient='records')

    # Build Excel File in memory for instant download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        raw_df.to_excel(writer, sheet_name='Original_CDR', index=False)
        processed_df.to_excel(writer, sheet_name='Processed_CDR', index=False)
        freq_df.to_excel(writer, sheet_name='Top_10_Calls_Pivot', index=False)
    
    output.seek(0)
    
    # Store temporary processed output in session / file cache if needed
    # For response payload:
    return jsonify({
        'status': 'success',
        'top_contacts': top_contacts,
        'imei_list': imei_list,
        'total_records': len(processed_df),
        'sample_records': processed_df.head(15).to_dict(orient='records')
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
