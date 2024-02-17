const socket = new WebSocket('ws://' + location.host + '/world_boss');

socket.addEventListener('message', ev =>
    {
        msg = JSON.parse(ev.data);
        document.getElementById('user_clicks').innerHTML = msg.single_clicks;
        document.getElementById('clicks_per_second').innerHTML = msg.clicks_per_second;
        document.getElementById('boss_name').innerHTML = msg.single_boss_name;
        document.getElementById('boss_health').innerHTML = msg.single_boss_health;
        document.getElementById('boss_image').src = "/static/"+msg.single_boss_path;
    });

document.getElementById('boss_image').onclick = (ev =>
    {
        socket.send(Array.from([1,1]));
    });