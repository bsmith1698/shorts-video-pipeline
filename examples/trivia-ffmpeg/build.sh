#!/bin/bash
set -e

SRC="${CLIPS_DIR:?Set CLIPS_DIR to your clip library (with VO/ and SFX/ subfolders)}"
R="${WORK_DIR:-$PWD/render}"
VO="$SRC/VO"
SFX="$SRC/SFX"
FB="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FI="/System/Library/Fonts/Supplemental/Impact.ttf"
FR="/System/Library/Fonts/Supplemental/Arial.ttf"

mkdir -p "$R/txt" "$R/seg"
cd "$R"

# ---------- text files ----------
cat > txt/intro1.txt <<'EOF'
5 QUESTIONS.
EOF
cat > txt/intro2.txt <<'EOF'
MOST PEOPLE GET
2 OR LESS.
EOF
cat > txt/intro3.txt <<'EOF'
KEEP SCORE IN
YOUR HEAD
EOF

cat > txt/q1.txt <<'EOF'
HOW MANY EARTHS COULD YOU FIT
INSIDE THE SUN?
EOF
cat > txt/r1.txt <<'EOF'
1.3 MILLION
EARTHS
EOF

cat > txt/q2.txt <<'EOF'
HOW MANY TEETH DOES A SHARK
GO THROUGH IN ITS LIFETIME?
EOF
cat > txt/r2.txt <<'EOF'
OVER 30,000
TEETH
EOF

cat > txt/q3.txt <<'EOF'
WHICH IS LONGER ON VENUS -
ONE DAY OR ONE YEAR?
EOF
cat > txt/r3.txt <<'EOF'
ONE DAY
LONGER THAN ITS YEAR
EOF

cat > txt/q4.txt <<'EOF'
WHICH COUNTRY HAS THE
MOST TIME ZONES?
EOF
cat > txt/r4.txt <<'EOF'
FRANCE
12 TIME ZONES
EOF

cat > txt/q5.txt <<'EOF'
HOW FAR DO BEES FLY TO MAKE
ONE POUND OF HONEY?
EOF
cat > txt/r5.txt <<'EOF'
55,000 MILES
EOF

cat > txt/outro1.txt <<'EOF'
COMMENT YOUR
SCORE OUT OF 5
EOF
cat > txt/outro2.txt <<'EOF'
5/5 = GENIUS
0/5 = OOF
EOF

printf '%s' "○ ○ ○ ○ ○" > txt/pip0.txt
printf '%s' "● ○ ○ ○ ○" > txt/pip1.txt
printf '%s' "● ● ○ ○ ○" > txt/pip2.txt
printf '%s' "● ● ● ○ ○" > txt/pip3.txt
printf '%s' "● ● ● ● ○" > txt/pip4.txt
printf '%s' "● ● ● ● ●" > txt/pip5.txt

echo "text files written"
