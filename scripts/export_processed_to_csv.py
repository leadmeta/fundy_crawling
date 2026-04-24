import sqlite3
import pandas as pd
import sys
import os
import json

def export_processed_db_to_csv(db_path='data/fundy_records.db', output_path='fundy_processed_exports.csv'):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        
        # Read the raw records (include site_name and url for context)
        query_raw = "SELECT id, site_name, title, url, details FROM funding_records"
        df_raw = pd.read_sql_query(query_raw, conn)
        
        # Read only SUCCESS processed records (skip SKIPPED/FAILED garbage)
        query_proc = "SELECT id, status, extracted_json, processed_at FROM processed_funding_records WHERE status = 'SUCCESS'"
        df_proc = pd.read_sql_query(query_proc, conn)
        
        # Merge them
        df = pd.merge(df_raw, df_proc, on='id', how='inner')
        
        # Truncate details for readability (full text is in the DB)
        df['details'] = df['details'].apply(lambda x: (x[:500] + '...') if isinstance(x, str) and len(x) > 500 else x)
        
        # Extract JSON fields into separate columns for better comparison
        def extract_json_fields(row):
            if pd.isna(row['extracted_json']) or not row['extracted_json']:
                return pd.Series({})
            try:
                data = json.loads(row['extracted_json'])
                # Convert list to string for better display in CSV/Excel
                for k, v in data.items():
                    if isinstance(v, list):
                        data[k] = ", ".join(v)
                return pd.Series(data)
            except Exception:
                return pd.Series({})

        # Apply extraction
        json_df = df.apply(extract_json_fields, axis=1)
        
        # Combine original with extracted fields
        result_df = pd.concat([df.drop('extracted_json', axis=1), json_df], axis=1)
        
        # Sort by processed_at descending
        result_df.sort_values(by='processed_at', ascending=False, inplace=True)
        
        # Export to CSV
        result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        # Export to Excel
        excel_path = output_path.replace('.csv', '.xlsx')
        
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
        result_df.to_excel(writer, sheet_name='ProcessedRecords', index=False)
        
        # Formatting
        workbook = writer.book
        worksheet = writer.sheets['ProcessedRecords']
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        
        for col_num, value in enumerate(result_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        worksheet.set_column('A:A', 15) # ID
        worksheet.set_column('B:B', 15) # site_name
        worksheet.set_column('C:C', 40, wrap_format) # title
        worksheet.set_column('D:D', 25) # url
        worksheet.set_column('E:E', 50, wrap_format) # details (truncated)
        worksheet.set_column('F:Z', 20, wrap_format) # Extracted fields
        
        writer.close()
        
        print(f"Successfully exported {len(result_df)} processed records to {output_path} and {excel_path}")
        
    except Exception as e:
        print(f"Failed to export Processed DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    export_processed_db_to_csv()
