import os
import urllib.request

fonts = {
    "Fraunces-Italic.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/fraunces/Fraunces%5Bopsz%2Cwght%5D.ttf", # Fraunces variable font containing weights
    "Oswald.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "Inter.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bslnt%2Cwght%5D.ttf"
}

dest_dir = os.path.join("frontend", "assets", "fonts")
os.makedirs(dest_dir, exist_ok=True)

print("Downloading fonts...")
for name, url in fonts.items():
    dest_path = os.path.join(dest_dir, name)
    try:
        print(f"Downloading {name}...")
        urllib.request.urlretrieve(url, dest_path)
        print(f"Successfully saved to {dest_path}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")

print("Done!")
