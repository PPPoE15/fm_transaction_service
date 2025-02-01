#!/bin/bash

set -euo pipefail


dephell_alive() {
   set +e
   dephell --help > /dev/null 2>&1
   ret=$?
   if [ $ret -ne 0 ]; then
        echo -e "${RedColor}dephell is not alive? Exiting${NC}..."
        exit 2
   else
        echo -e "${GreenColor}dephell looks Ok${NC}..."
   fi
   set -e

}


dephell_convert(){

    local requirements_file
    local tmpfile

    requirements_file=$1
    tmpfile=$2

    # generate setup.py from requirements.txt
    dephell deps convert --from "$requirements_file" --to-format setuppy --to-path "$tmpfile"

}


get_item() {

    local searching_item
    local tmpfile

    searching_item=$1
    tmpfile=$2

    # sed gets rid of whitespaces by the first occasion
    FOUND_ITEM=$(grep -E "$searching_item.*=.*\[" "$tmpfile" | sed -e 's/^[ \t]*//')

}


found_item_checker() {

    if [[ -z $FOUND_ITEM ]];
    then
        echo -e "${RedColor}FOUND_ITEM variable is empty. It's too dangerous continue, exiting${NC}...";
    fi

}


replace_item() {

    local item_to_search
    local replacement_item
    local file_name_to_convert_to

    item_to_search=$1
    replacement_item=$2
    file_name_to_convert_to=$3

    sed -i "s;${item_to_search}.*=.*\[.*].*$;${replacement_item};g" "$file_name_to_convert_to"

}


cleanup() {

   rm -rf "$FILE_NAME_CONVERTED_TMPFILE" 

}


_main() {

    RedColor='\033[0;31m'
    GreenColor='\033[0;32m'
    NC='\033[0m'

    dephell_alive

    FILE_NAME_TO_CONVERT_FROM=requirements.txt
    FILE_NAME_TO_CONVERT_TO=setup.py
    FILE_NAME_CONVERTED_TMPFILE=$(mktemp -p ./)
    ALL_ITEMS_TO_SEARCH=( "packages" "install_requires" )

    dephell_convert "$FILE_NAME_TO_CONVERT_FROM" "$FILE_NAME_CONVERTED_TMPFILE"

    for item_to_search in "${ALL_ITEMS_TO_SEARCH[@]}";
    do
        get_item "$item_to_search" "$FILE_NAME_CONVERTED_TMPFILE"
        found_item_checker
        replace_item "$item_to_search" "$FOUND_ITEM" "$FILE_NAME_TO_CONVERT_TO"
    done

    trap cleanup EXIT
    trap cleanup SIGINT

}


_main

