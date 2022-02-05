// https://wrightshq.com/playground/placing-multiple-markers-on-a-google-map-using-api-3/
// https://github.com/googlemaps/js-marker-clusterer
// https://developers.google.com/maps/documentation/javascript/marker-clustering

jQuery(function($) {
    // Asynchronously Load the map API
    var script = document.createElement('script');
    script.src = "//maps.googleapis.com/maps/api/js?key={{api_key}}&callback=initialize";
    document.body.appendChild(script);
});

let map;
let markers = [];
let markerCluster;


function draw_markers(locations) {
    const infoWindow = new google.maps.InfoWindow({
        content: "",
        disableAutoPan: true,
    });

   markers = locations.map((item, i) => {
    const label = item[0];
    const marker = new google.maps.Marker({
      position: new google.maps.LatLng(item[1], item[2]),
      label,
    });

    const hwModel = item[3];
    const snr = item[4];
    const lastHeard = item[5];
    const batteryLevel = item[6];
    const altitude = item[7];
    // markers can only be keyboard focusable when they have click listeners
    // open info window when marker is clicked
    const urlSearchParams = new URLSearchParams(window.location.search);
    const params = Object.fromEntries(urlSearchParams.entries())
    href = window.location.search;
    if ( params['name'] == undefined ) {
        if ( href.length > 0 ) {
            href += '&name=' + label
        } else {
            href += '?name=' + label
        }
    }
    marker.addListener("click", () => {
      infoWindow.setContent('<div><a href="' + href + '">' + label + '</a>' +
                            '<hr>' +
                            'Last heard: ' + lastHeard +
                            '<br>HW Model: ' + hwModel +
                            '<br>SNR: ' + snr +
                            '<br>Battery level: ' + batteryLevel + '% ' +
                            '<br>Altitude: ' + altitude + 'm ' +
      '</div>');
      infoWindow.open(map, marker);
    });
    return marker;
  });

}

function getMarkers() {
    console.log('(Re)drawing markers...');
    $.get('/data.json' + window.location.search, function(data) {
        // clear
        markerCluster.clearMarkers();
        markerCluster.setMap(null);
        markers = [];
        // (re)draw
        draw_markers(data);
        markerCluster.markers = markers;
        markerCluster.setMap(map);
    });
}


function initialize() {
    var center = new google.maps.LatLng({{center_latitude}}, {{center_longitude}});
    // global
    map = new google.maps.Map(document.getElementById('map'), {
          zoom: 10,
          center: center,
          scaleControl: true,
          mapTypeId: google.maps.MapTypeId.ROADMAP,
          mapTypeControl: true,
          mapTypeControlOptions: {
            style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
            mapTypeIds: ["roadmap", "satellite"],
          },
        });

    // global
    markerCluster = new markerClusterer.MarkerClusterer({ map, markers });
    getMarkers();
    setInterval(getMarkers, {{redraw_markers_every}}000);
}
