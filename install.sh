dir="/home/modra/.config/autostart"
filename="$dir/creelmt-winder-tray.desktop"

if ! [ -d $dir ]; then
    echo "creating directory $dir"
    mkdir $dir
fi

if [ -f $filename ]; then
    echo "deleting existing file @ $filename"
    rm $filename
fi

echo "Writing to $filename"
echo "\
[Desktop Entry]
Type=Application
Name=CreelMT Winder Tray
Exec=/usr/bin/python3 /home/modra/code/rpi_tray_widget/main.py creelmt-winder-display.service
X-GNOME-Autostart-enabled=true" >> $filename

cat $filename

echo "Done"
