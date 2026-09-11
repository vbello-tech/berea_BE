python manage.py migrate &&
python manage.py load_bible_json &&
python manage.py load_bible_json --file /Users/vbellotech/Desktop/START\ UP/Berea/Berea_BE/berea/bible/fixtures/kjv/bsb_bible.json --translation BSB &&
python manage.py load_strongs &&
python manage.py load_tagged_greek_nt &&
python manage.py load_tagged_hebrew_ot &&
python manage.py load_tagged_greek_nt --translation BSB &&
python manage.py load_tagged_hebrew_ot --translation BSB &&
python manage.py add_psalm_superscriptions &&
python manage.py add_psalm_superscriptions --translation BSB &&
python manage.py load_cross_references &&
python manage.py load_cross_references --translation BSB




# ignore this commands for now.
python manage.py load_kjv_strongs_tags
python manage.py load_kjv_strongs_tags_from_sword --file /Users/vbellotech/Desktop/START\ UP/Berea/Berea_BE/berea/bible/fixtures/kjv_interlinear/kjv_strongs.json --clear
python manage.py load_kjv_strongs_richtags --ot-file /Users/vbellotech/Desktop/START\ UP/Berea/Berea_BE/berea/bible/fixtures/kjv_hnt_got/kjv_TAHOT_merged.txt --nt-file /Users/vbellotech/Desktop/START\ UP/Berea/Berea_BE/berea/bible/fixtures/kjv_hnt_got/kjv_TAGNT_merged.txt   --clear



