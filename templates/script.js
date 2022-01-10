// https://wrightshq.com/playground/placing-multiple-markers-on-a-google-map-using-api-3/
// https://github.com/googlemaps/js-marker-clusterer
// https://developers.google.com/maps/documentation/javascript/marker-clustering

jQuery(function($) {
    // Asynchronously Load the map API
    var script = document.createElement('script');
    script.src = "//maps.googleapis.com/maps/api/js?key={{api_key}}&callback=initialize";
    document.body.appendChild(script);
});

function draw_markers(locations, map) {
    const infoWindow = new google.maps.InfoWindow({
        content: "",
        disableAutoPan: true,
    });

  const markers = locations.map((item, i) => {
    const label = item[0];
    const marker = new google.maps.Marker({
      position: new google.maps.LatLng(item[1], item[2]),
      label,
    });

    // markers can only be keyboard focusable when they have click listeners
    // open info window when marker is clicked
    marker.addListener("click", () => {
      infoWindow.setContent(label);
      infoWindow.open(map, marker);
    });
    return marker;
  });


    //new MarkerClusterer({ markers, map });
    const markerCluster = new markerClusterer.MarkerClusterer({ map, markers });
}

function initialize() {
     var center = new google.maps.LatLng(51.5074, 0.1278);
        var map = new google.maps.Map(document.getElementById('map_canvas'), {
          zoom: 3,
          center: center,
          mapTypeId: google.maps.MapTypeId.ROADMAP
        });

    $.get('/data.json', function(data) {
        draw_markers(data, map);
    });
}
