from PIL import Image
import os
from datetime import datetime

def combine_images_to_pdf():
    # Get today's date in YYYYMMDD format
    today = datetime.now().strftime("%Y%m%d")
    
    # Define the folder path
    folder_path = f"./static/images/{today}"
    
    # Check if the folder exists
    if not os.path.exists(folder_path):
        print(f"Folder {folder_path} does not exist")
        return
    
    # Get all PNG files from the folder
    png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    
    if not png_files:
        print("No PNG files found in the folder")
        return
    
    # Open all images and convert to RGB (PDF requires RGB)
    images = []
    for png_file in png_files:
        image_path = os.path.join(folder_path, png_file)
        try:
            image = Image.open(image_path)
            # Convert RGBA to RGB if necessary
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            images.append(image)
        except Exception as e:
            print(f"Error processing {png_file}: {str(e)}")
    
    if not images:
        print("No valid images to process")
        return
    
    # Create PDF file path
    pdf_path = os.path.join(folder_path, f"combined_{today}.pdf")
    
    try:
        # Save the first image as PDF with the rest appended
        images[0].save(
            pdf_path,
            "PDF",
            save_all=True,
            append_images=images[1:]
        )
        print(f"PDF created successfully: {pdf_path}")
    except Exception as e:
        print(f"Error creating PDF: {str(e)}")

if __name__ == "__main__":
    combine_images_to_pdf()