from bs4 import BeautifulSoup
from datetime import datetime

def combine_daily_emails():
    """Combine all daily email HTML tables into one file."""
    
    # CSS style that will be shared across all tables
    css_style = '''
        <style>
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .stock-link {
                color: #0066cc;
                text-decoration: none;
            }
            .email-container {
                max-width: 1000px;
                margin: 0 auto;
                font-family: Arial, sans-serif;
            }
            .section {
                margin-bottom: 30px;
            }
        </style>
    '''
    
    # Start the combined HTML document
    current_date = datetime.now().strftime("%Y-%m-%d")
    combined_html = f'''
    <html>
    <head>
        <title>StockWise Daily Analysis - {current_date}</title>
        {css_style}
    </head>
    <body>
        <div class="email-container">
        <h1>StockWise Daily Analysis - {current_date}</h1>
    '''
    
    # List of files to combine
    files = [
        ('Volume Analysis', './static/daily_email_volume.txt'),
        ('RSI Analysis', './static/daily_email_rsi.txt'),
        ('Buy Points Analysis', './static/daily_email_buypoint.txt')
    ]
    
    # Process each file
    for title, filepath in files:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                
            # Parse the HTML content
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract just the table and its header
            table = soup.find('table')
            header = soup.find('h2')
            
            if table and header:
                combined_html += f'''
                <div class="section">
                    {str(header)}
                    {str(table)}
                </div>
                '''
            
        except Exception as e:
            print(f"Error processing {filepath}: {str(e)}")
            continue
    
    # Close the HTML document
    combined_html += '''
        </div>
    </body>
    </html>
    '''
    
    # Save the combined file
    with open('./static/daily_email_combined.txt', 'w') as f:
        f.write(combined_html)

if __name__ == "__main__":
    combine_daily_emails()