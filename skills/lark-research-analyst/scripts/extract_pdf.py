import os
import sys
import json
import argparse
import subprocess
import shutil

def is_tool_installed(name):
    """Check whether `name` is on PATH and marked as executable."""
    return shutil.which(name) is not None

def extract_with_mineru(pdf_path, output_dir, txt_path, manifest_path):
    """Extract PDF using MinerU CLI (High Quality)"""
    print("MinerU is installed. Using MinerU for high-quality extraction...")
    
    # MinerU outputs to a specific directory structure, we need to adapt to it
    mineru_out_dir = os.path.join(output_dir, "mineru_out")
    if not os.path.exists(mineru_out_dir):
        os.makedirs(mineru_out_dir)
        
    cmd = ["mineru", "-f", pdf_path, "-o", mineru_out_dir]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # MinerU usually creates a subfolder with the PDF name
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        result_dir = os.path.join(mineru_out_dir, pdf_basename)
        
        if not os.path.exists(result_dir):
            # Fallback if structure is different
            result_dir = mineru_out_dir
            
        # Find the generated markdown file
        md_file = None
        for file in os.listdir(result_dir):
            if file.endswith(".md"):
                md_file = os.path.join(result_dir, file)
                break
                
        if md_file:
            # Copy content to txt_path
            with open(md_file, 'r', encoding='utf-8') as src, open(txt_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        else:
            print("Warning: Could not find Markdown output from MinerU. Falling back to PyMuPDF.")
            return extract_with_pymupdf(pdf_path, output_dir, txt_path, manifest_path)
            
        # Build image manifest from MinerU output
        image_manifest = []
        img_dir = os.path.join(result_dir, "images")
        if os.path.exists(img_dir):
            for i, img_file in enumerate(os.listdir(img_dir)):
                img_path = os.path.join(img_dir, img_file)
                # MinerU extracts images, we map them to our manifest format
                image_manifest.append({
                    "id": f"img_{i}",
                    "filename": img_file,
                    "path": img_path,
                    "type": os.path.splitext(img_file)[1].lstrip('.')
                })
                
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(image_manifest, f, indent=2, ensure_ascii=False)
            
        print(f"MinerU extraction completed. Found {len(image_manifest)} images.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"MinerU extraction failed: {e.stderr}")
        print("Falling back to PyMuPDF extraction...")
        return extract_with_pymupdf(pdf_path, output_dir, txt_path, manifest_path)
    except Exception as e:
        print(f"Error running MinerU: {e}")
        print("Falling back to PyMuPDF extraction...")
        return extract_with_pymupdf(pdf_path, output_dir, txt_path, manifest_path)

def extract_with_pymupdf(pdf_path, output_dir, txt_path, manifest_path):
    """Extract PDF using PyMuPDF (Fast, Self-contained fallback)"""
    print("Using PyMuPDF for fast local extraction...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Error: PyMuPDF (fitz) is not installed.")
        print("Please install it using: pip install PyMuPDF")
        sys.exit(1)
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    doc = fitz.open(pdf_path)
    full_text = []
    image_manifest = []
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        text = page.get_text("text", sort=True)
        full_text.append(f"--- Page {page_index + 1} ---\n{text}")
        
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            image_filename = f"page{page_index+1}_img{img_index+1}.{image_ext}"
            image_save_path = os.path.join(output_dir, image_filename)
            
            with open(image_save_path, "wb") as f:
                f.write(image_bytes)
            
            image_manifest.append({
                "page": page_index + 1,
                "filename": image_filename,
                "path": image_save_path,
                "type": image_ext
            })

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(image_manifest, f, indent=2, ensure_ascii=False)

    print(f"Extracted text to {txt_path}")
    print(f"Extracted {len(image_manifest)} images to {output_dir}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Smart PDF Extractor (MinerU -> PyMuPDF fallback)")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output-dir", default="assets/images", help="Directory to save extracted images")
    parser.add_argument("--txt-path", default="extracted_text.txt", help="Path to save extracted text")
    parser.add_argument("--manifest-path", default="image_manifest.json", help="Path to save image manifest JSON")
    parser.add_argument("--force-local", action="store_true", help="Force use PyMuPDF even if MinerU is installed")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_path):
        print(f"Error: File not found: {args.pdf_path}")
        sys.exit(1)
        
    # Strategy: Try MinerU first, fallback to PyMuPDF
    if not args.force_local and is_tool_installed("mineru"):
        extract_with_mineru(args.pdf_path, args.output_dir, args.txt_path, args.manifest_path)
    else:
        extract_with_pymupdf(args.pdf_path, args.output_dir, args.txt_path, args.manifest_path)

if __name__ == "__main__":
    main()