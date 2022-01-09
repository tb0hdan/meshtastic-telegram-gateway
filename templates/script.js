// https://wrightshq.com/playground/placing-multiple-markers-on-a-google-map-using-api-3/
// https://github.com/googlemaps/js-marker-clusterer
// https://developers.google.com/maps/documentation/javascript/marker-clustering

jQuery(function($) {
    // Asynchronously Load the map API
    var script = document.createElement('script');
    script.src = "//maps.googleapis.com/maps/api/js?key={{api_key}}&callback=initialize";
    document.body.appendChild(script);
});

function draw_markers(markers, map) {
        var rmarkers = [];
        for( i = 0; i < markers.length; i++ ) {
            var marker = new google.maps.Marker({
                position: new google.maps.LatLng(markers[i][1], markers[i][2]),
                map,
                title: markers[i][0]
            });
            var contentString = '<div id="content"><div id="sideNotice"></div><div id="bodyContent">' + markers[i][0] + '</div></div>';

            var infowindow = new google.maps.InfoWindow({
                content: contentString
            });

            marker.addListener("click", () => {
                infowindow.open({
                  anchor: marker,
                  map,
                  shouldFocus: false
                });
            });

            rmarkers.push(marker);
        };

        var options = {
            imagePath: '/static/images/m'
        };
        var markerCluster = new MarkerClusterer(map, rmarkers, options);
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
