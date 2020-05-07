DRIVES="$HOME/drives"

mkdir -p $DRIVES/one
mkdir -p $DRIVES/two
mkdir -p $DRIVES/three
mkdir -p $DRIVES/four

sudo mount /dev/sda4 $DRIVES/one -o uid=$(id -u $USER)
sudo mount /dev/sda6 $DRIVES/two -o uid=$(id -u $USER)
sudo mount /dev/sda7 $DRIVES/three -o uid=$(id -u $USER)
sudo mount /dev/sda8 $DRIVES/four -o uid=$(id -u $USER)

