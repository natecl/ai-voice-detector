"""Build a local macOS app bundle; does not install or publish anything."""
import plistlib
import tempfile
import shutil
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DESTINATION=ROOT.parent/'outputs/Voice Check.app'
staging=tempfile.TemporaryDirectory(prefix='voice-check-build-')
BUNDLE=Path(staging.name)/'Voice Check.app'
contents=BUNDLE/'Contents'
(contents/'MacOS').mkdir(parents=True,exist_ok=True)
plist={
 'CFBundleName':'Voice Check', 'CFBundleDisplayName':'Voice Check',
 'CFBundleIdentifier':'local.natecl.voice-check', 'CFBundleVersion':'1',
 'CFBundleShortVersionString':'0.1.0', 'CFBundleExecutable':'VoiceCheck',
 'CFBundlePackageType':'APPL', 'LSMinimumSystemVersion':'13.0', 'LSUIElement':True,
 'NSAudioCaptureUsageDescription':'Listen to system audio for local synthetic-speech detection. No screen images are saved.',
 'NSScreenCaptureUsageDescription':'Capture system audio for local voice analysis. Screen frames are not consumed or saved.',
 'NSMicrophoneUsageDescription':'Record your voice for local human or AI audio detection. Audio stays on your Mac.',
 'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True},
 'VoiceCheckProjectPath':str(ROOT),
}
(contents/'Info.plist').write_bytes(plistlib.dumps(plist))
subprocess.run(['swiftc',str(ROOT/'desktop/main.swift'),str(ROOT/'desktop/SystemAudioCapture.swift'),'-o',str(contents/'MacOS/VoiceCheck'),
                '-framework','AppKit','-framework','WebKit','-framework','UniformTypeIdentifiers','-framework','ScreenCaptureKit','-framework','AVFoundation'],check=True)
# Finder may decorate new .app directories; remove only signing-incompatible metadata.
for path in [BUNDLE, *BUNDLE.rglob('*')]:
    for attr in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        if subprocess.run(['xattr','-p',attr,str(path)],capture_output=True).returncode == 0:
            subprocess.run(['xattr','-d',attr,str(path)],check=True)
subprocess.run(['codesign','--force','--sign','-',str(BUNDLE)],check=True)
shutil.copytree(BUNDLE,DESTINATION,dirs_exist_ok=True)
for path in [DESTINATION, *DESTINATION.rglob('*')]:
    for attr in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        if subprocess.run(['xattr','-p',attr,str(path)],capture_output=True).returncode == 0:
            subprocess.run(['xattr','-d',attr,str(path)],check=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(DESTINATION)],check=True)
staging.cleanup()
print(DESTINATION)
