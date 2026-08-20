#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repository=$(cd "$script_dir/../../.." && pwd)
workspace=${GAPFILL_NATIVE_WORKSPACE:-/tmp/gapfill-krita-native-build}
production="$workspace/production"
source_root="$workspace/source/krita-858d352"
build_root="$workspace/build/krita-exact-5"
prefix="$workspace/deps/official-prefix"
toolchain="$workspace/toolchain/llvm-mingw/bin"
python_source="$workspace/source/cpython-3.13.5"
python_import="$production/lib/libpython313.dll.a"
python_config="$workspace/spike/include/pyconfig.h"
module=gapfill_krita_native_5_3_3.cp313-win_amd64.pyd

test -f "$build_root/lib/libkritaui.dll.a"
test -f "$build_root/lib/libkritaimage.dll.a"
test -f "$build_root/lib/libkritapigment.dll.a"
test -f "$build_root/lib/libkritacommand.dll.a"
test -f "$build_root/lib/libkritaversion.dll.a"
test -f "$prefix/lib/libQt5Core.a"

mkdir -p \
    "$production/lib" \
    "$production/build-a" \
    "$production/build-b" \
    "$production/out" \
    "$(dirname "$python_config")"
printf '#include "%s"\n' "$python_source/PC/pyconfig.h.in" > "$python_config"
test ! -e "$production/build-a/$module"
test ! -e "$production/build-b/$module"

"$toolchain/llvm-dlltool" \
    -m i386:x86-64 \
    -D python313.dll \
    -d "$repository/krita-plugin/native/krita_5_3_3/python313.def" \
    -l "$python_import"

compile_one() {
    output=$1
    "$toolchain/x86_64-w64-mingw32-clang++" \
        -std=gnu++17 \
        -O2 \
        -g \
        -gdwarf-aranges \
        -fexceptions \
        -fno-operator-names \
        -fvisibility=hidden \
        -fvisibility-inlines-hidden \
        -frandom-seed=gapfill-krita-native-5-3-3-production \
        -ffile-prefix-map="$workspace"=/build/gapfill-krita-native \
        -fdebug-prefix-map="$workspace"=/build/gapfill-krita-native \
        -DNDEBUG \
        -DBOOST_ALL_NO_LIB \
        -DNOMINMAX \
        -DQT_CORE_LIB \
        -DQT_GUI_LIB \
        -DQT_WIDGETS_LIB \
        -DQT_NO_DEBUG \
        -DQT_NO_SIGNALS_SLOTS_KEYWORDS \
        -DUNICODE \
        -D_UNICODE \
        -DWIN32_LEAN_AND_MEAN \
        -D_WIN32_WINNT=0x0602 \
        -DWINVER=0x0602 \
        -D_WIN32_IE=0x0602 \
        -I"$workspace/spike/include" \
        -I"$python_source/Include" \
        -I"$build_root" \
        -I"$source_root" \
        -I"$build_root/libs/ui" \
        -I"$source_root/libs/ui" \
        -I"$build_root/libs/version" \
        -I"$source_root/libs/version" \
        -I"$build_root/libs/image" \
        -I"$source_root/libs/image" \
        -I"$source_root/libs/image/commands_new" \
        -I"$build_root/libs/pigment" \
        -I"$source_root/libs/pigment" \
        -I"$source_root/libs/pigment/resources" \
        -I"$source_root/libs/pigment/compositeops" \
        -I"$build_root/libs/resources" \
        -I"$source_root/libs/resources" \
        -I"$build_root/libs/flake" \
        -I"$source_root/libs/flake" \
        -I"$source_root/libs/flake/commands" \
        -I"$source_root/libs/flake/resources" \
        -I"$build_root/libs/widgets" \
        -I"$source_root/libs/widgets" \
        -I"$build_root/libs/impex" \
        -I"$source_root/libs/impex" \
        -I"$build_root/libs/psdutils" \
        -I"$source_root/libs/psdutils" \
        -I"$build_root/libs/command" \
        -I"$source_root/libs/command" \
        -I"$build_root/libs/global" \
        -I"$source_root/libs/global" \
        -I"$build_root/libs/widgetutils" \
        -I"$source_root/libs/widgetutils" \
        -I"$source_root/libs/widgetutils/config" \
        -I"$source_root/libs/widgetutils/xmlgui" \
        -isystem "$prefix/include" \
        -isystem "$prefix/include/boost-1_90" \
        -isystem "$prefix/include/Imath" \
        -isystem "$prefix/include/eigen3" \
        -isystem "$prefix/include/QtCore" \
        -isystem "$prefix/include/QtGui" \
        -isystem "$prefix/include/QtWidgets" \
        -isystem "$prefix/include/QtXml" \
        -isystem "$prefix/mkspecs/win32-clang-g++" \
        -isystem "$prefix/include/KF5" \
        -isystem "$prefix/include/KF5/KI18n" \
        -isystem "$prefix/include/KF5/KConfig" \
        -isystem "$prefix/include/KF5/KConfigCore" \
        -isystem "$prefix/include/KF5/KCoreAddons" \
        -shared \
        -Wl,--dynamicbase \
        -Wl,--nxcompat \
        -Wl,--disable-auto-image-base \
        -Wl,--high-entropy-va \
        -Wl,--no-insert-timestamp \
        -Wl,--image-base,0x180000000 \
        "$repository/krita-plugin/native/krita_5_3_3/gapfill_krita_native_5_3_3.cpp" \
        -L"$production/lib" \
        -L"$build_root/lib" \
        -L"$prefix/lib" \
        -lpython313 \
        -lkritaui \
        -lkritaimage \
        -lkritapigment \
        -lkritacommand \
        -lkritaversion \
        -lkritaglobal \
        -lQt5Widgets \
        -lQt5Gui \
        -lQt5Xml \
        -lQt5Core \
        -lKF5I18n \
        -lKF5ConfigCore \
        -lKF5CoreAddons \
        -o "$output"
}

compile_one "$production/build-a/$module"
compile_one "$production/build-b/$module"

cmp "$production/build-a/$module" "$production/build-b/$module"
cp "$production/build-a/$module" "$production/out/$module"

sha256sum \
    "$production/build-a/$module" \
    "$production/build-b/$module" \
    "$production/out/$module"
