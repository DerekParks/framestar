#!/usr/bin/env bash
# Builds kiosk/build/framestar-kiosk.apk without Gradle. Needs a JDK plus Android build-tools 34 and platform 34.
# FRAMESTAR_URL sets the URL used until one is sent with a VIEW intent.
set -euo pipefail
cd "$(dirname "$0")"

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
URL="${FRAMESTAR_URL:-http://10.0.0.117:8000/}"
BT="$ANDROID_HOME/build-tools/34.0.0"
JAR="$ANDROID_HOME/platforms/android-34/android.jar"
KS="${FRAMESTAR_KEYSTORE:-$HOME/.android/framestar-kiosk.keystore}"

rm -rf build && mkdir -p build/gen build/classes build/res/values
cp -r res/. build/res/
cat > build/res/values/url.xml <<XML
<?xml version="1.0" encoding="utf-8"?>
<resources><string name="default_url" translatable="false">$URL</string></resources>
XML

"$BT/aapt2" compile --dir build/res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml build/res.zip \
  --java build/gen --min-sdk-version 23 --target-sdk-version 23 --version-code 1 --version-name 1.0
"${JAVA_HOME:+$JAVA_HOME/bin/}javac" -nowarn --release 8 -Xlint:-options -classpath "$JAR" -d build/classes \
  $(find src build/gen -name '*.java')
"$BT/d8" --min-api 23 --lib "$JAR" --output build $(find build/classes -name '*.class')
(cd build && zip -qj base.apk classes.dex)
"$BT/zipalign" -f 4 build/base.apk build/aligned.apk

if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -storepass android -keypass android -alias framestar \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=framestar kiosk" >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android --out build/framestar-kiosk.apk build/aligned.apk
echo "Built $(pwd)/build/framestar-kiosk.apk -> $URL"
