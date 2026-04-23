import sqlite3
import pandas as pd
import sys
import os

def export_db_to_csv(db_path='data/fundy_records.db', output_path='fundy_exports.csv'):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
        
    try:
        # Create connection via sqlite3
        conn = sqlite3.connect(db_path)
        
        # Read the table directly into pandas DataFrame
        # Sort by date descending (latest first) per user request. 
        # Perform LEFT JOIN to merge the normalized dictionary tables back into text
        query = """
        SELECT 
            f.id, f.site_name, f.title, f.date, 
            i1.name as institution, 
            i2.name as operating_agency, 
            f.recruit_period, f.deadline, f.event_period, 
            c.name as category, 
            t.name as target_audience, 
            ind.name as industry, 
            f.target_age, f.corporate_type, 
            r.name as region, 
            f.details, f.benefits, f.evaluation_method, 
            f.startup_history, f.exclusion_criteria, 
            f.attachments, f.attachment_names, f.apply_method, 
            f.documents, f.contact_agency, f.contact_phone, f.contact_email, f.url
        FROM funding_records f
        LEFT JOIN institution_dict i1 ON f.institution_id = i1.id
        LEFT JOIN institution_dict i2 ON f.operating_agency_id = i2.id
        LEFT JOIN category_dict c ON f.category_id = c.id
        LEFT JOIN target_audience_dict t ON f.target_audience_id = t.id
        LEFT JOIN industry_dict ind ON f.industry_id = ind.id
        LEFT JOIN region_dict r ON f.region_id = r.id
        ORDER BY f.date DESC
        """
        
        df = pd.read_sql_query(query, conn)
        
        # Deduplication check just in case (we already do it by ID globally)
        df.drop_duplicates(subset=['id'], inplace=True)
        
        # Export to CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        # Export to Excel as well
        excel_path = output_path.replace('.csv', '.xlsx')
        
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='FundingRecords', index=False)
        
        # Access the XlsxWriter workbook and worksheet objects.
        workbook = writer.book
        worksheet = writer.sheets['FundingRecords']
        
        # Add a format for text wrap
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        
        # Write headers with custom format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # Set column widths
        worksheet.set_column('A:B', 15) # ID, Site Name
        worksheet.set_column('C:C', 50, wrap_format) # Title
        worksheet.set_column('D:I', 20) # Dates, Categories
        worksheet.set_column('O:O', 80, wrap_format) # Details (Very wide)
        worksheet.set_column('P:R', 40, wrap_format) # Benefits, Eval, History
        
        writer.close()
        
        print(f"Successfully exported {len(df)} records to {output_path} and {excel_path}")
        
    except Exception as e:
        print(f"Failed to export DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    export_db_to_csv()
