/**** Start of imports. If edited, may not auto-convert in the playground. ****/
var temp = ee.ImageCollection(
    "projects/example_project_folder/assets/sresa1b_ncar_pcm1_1_monthly_tavg_1950-2099"
  ),
  prec = ee.ImageCollection(
    "projects/example_project_folder/assets/sresa1b_ncar_pcm1_1_monthly_prcp_1950-2099"
  ),
  points = ee.FeatureCollection('WCMC/WDPA/current/points');
/***** End of imports. If edited, may not auto-convert in the playground. *****/
//// Constants
var TEMP = "sresa1b_ncar_pcm1_1_monthly_tavg_1950-2099";
var PREC = "sresa1b_ncar_pcm1_1_monthly_prcp_1950-2099";

var TEMP_VIS_MIN = -30;
var TEMP_VIS_MAX = 30;
var PREC_VIS_MIN = 0;
var PREC_VIS_MAX = 10;

var COMPOSITE_DOWNLOAD_SCALE = 10000;

var TITLE_STYLE = {
  fontWeight: "bold",
  fontSize: "32px",
  padding: "10px",
  color: "#262223",
};

var PARAGRAPH_STYLE = {
  fontSize: "14px",
  fontWeight: "bold",
  color: "#595959",
  padding: "10px",
};

var LABEL_STYLE = {
  fontSize: "14px",
  fontWeight: "bold",
};

var INSTRUCTIONS_STYLE = {
  fontSize: "14px",
  fontWeight: "bold",
  color: "red",
  padding: "8px",
};

var ERROR_MESSAGE_STYLE = {
  fontSize: "14px",
  fontWeight: "bold",
  color: "white",
  padding: "8px",
  backgroundColor: "red",
  position: "top-center",
};

var LEGEND_TITLE_STYLE = {
  fontSize: "20px",
  fontWeight: "bold",
  stretch: "horizontal",
  textAlign: "center",
  margin: "4px",
};

//// Globals (needed by multiple functions)
var mapPanel = ui.Map();
var mapLayers = mapPanel.layers();
var drawingTools = mapPanel.drawingTools();
var drawingLayers = drawingTools.layers();
var inspectorChangeHandler = ui.util.debounce(
  inspectorChangeHandlerInternal,
  100
);

//Left panel widgets read by event handlers
var datasetSelect = ui.Select({
  items: [TEMP, PREC],
  placeholder: "[Select Climatological Dataset...]",
  onChange: inspectorChangeHandler,
});
var clearWorkspaceButton = ui.Button({
  label: "CLEAR WORKSPACE",
  onClick: clearWorkspaceHandler,
});
var pointsInAOISelect1 = ui.Select({
  placeholder: "Points in AOI 1...",
  onChange: getPointSelectHandler(0),
});
var pointsInAOISelect2 = ui.Select({
  placeholder: "Points in AOI 2...",
  onChange: getPointSelectHandler(1),
});
var radiusInKmBox = ui.Textbox({ value: 10 });
var startDate = ui.Textbox("YYYY-MM-DD", "2012-01-01");
var endDate = ui.Textbox("YYYY-MM-DD", "2012-12-31");
var minStats = ui.Checkbox({ label: "Minimum", value: true });
var maxStats = ui.Checkbox({ label: "Maximum", value: true });
var meanStats = ui.Checkbox({ label: "Average", value: true });
var graphPanel = ui.Panel();

(function setInitialUI() {
  mapLayers.add(
    ui.Map.Layer({
      eeObject: points,
      name: "Points",
      shown: true,
    }).setVisParams({ color: "006600" })
  );

  drawingTools.addLayer([], "Area of Interest (AOI) 1", "red");
  drawingTools.addLayer([], "Area of Interest (AOI) 2", "blue");
  drawingTools.onDraw(inspectorChangeHandler);
  drawingTools.onEdit(inspectorChangeHandler);
  drawingTools.setDrawModes(["polygon"]);
  drawingTools.setShape("polygon");

  //Define Texts and Labels for left panel
  var titleLabel = ui.Label("Climate Time-series Analysis", TITLE_STYLE);
  var descriptionText =
    "This app allows you to generate a time-series analysis " +
    "showing changes in temperature or precipitation over time. ";
  var descriptionLabel = ui.Label(descriptionText, PARAGRAPH_STYLE);
  var instructionsText =
    "INSTRUCTIONS:\n" +
    "1) Select climatological dataset for analysis\n" +
    "2) Select Start and End dates\n" +
    "3) Choose the type of statistical analysis\n" +
    "4) Draw a polygon on the map\n" +
    '5) (Optional) To compare two AOIs: hover over the "Area of Interest (AOI) 1"\n' +
    " label and select AOI 2 from the dropdown, then repeat step 4 to draw another AOI\n";
  var instructionsLabel = ui.Label(instructionsText, { whiteSpace: "pre" });
  var pointsLabel = ui.Label(
    "(Optional) select a point from the dropdown menu(s) to replace " +
      "the drawn AOI with the given radius around the selected point:",
    LABEL_STYLE
  );
  var radiusLabel = ui.Label("Radius (in km):");
  var selectAnalysisLabel = ui.Label(
    "Select the type of analysis you would like to perform:",
    LABEL_STYLE
  );
  var startDateLabel = ui.Label("Start date:");
  var endDateLabel = ui.Label("End date:");

  var inspectorPanel = ui.Panel({ style: { width: "30%" } });
  inspectorPanel
    .add(titleLabel)
    .add(descriptionLabel)
    .add(instructionsLabel)
    .add(datasetSelect)
    .add(clearWorkspaceButton)
    .add(pointsLabel)
    .add(pointsInAOISelect1)
    .add(pointsInAOISelect2)
    .add(radiusLabel)
    .add(radiusInKmBox)
    .add(selectAnalysisLabel)
    .add(startDateLabel)
    .add(startDate)
    .add(endDateLabel)
    .add(endDate)
    .add(minStats)
    .add(maxStats)
    .add(meanStats)
    .add(graphPanel);

  ui.root.clear();
  ui.root.add(ui.SplitPanel(inspectorPanel, mapPanel));
})();

function inspectorChangeHandlerInternal() {
  var aois = [
    drawingLayers.get(0).toGeometry(),
    drawingLayers.get(1).toGeometry(),
  ];
  if (
    drawingLayers.get(0).geometries().length() === 0 &&
    drawingLayers.get(1).geometries().length() === 0
  ) {
    // No AOI selected
    return;
  }
  resetMapLayers();
  graphPanel.clear();
  filterPointsInAOI(pointsInAOISelect1, aois[0]);
  filterPointsInAOI(pointsInAOISelect2, aois[1]);

  var dataset, visOptions, chartOptions;
  if (datasetSelect.getValue() === TEMP) {
    dataset = temp;
    visOptions = {
      min: TEMP_VIS_MIN,
      max: TEMP_VIS_MAX,
      palette: ["blue", "limegreen", "yellow", "darkorange", "red"],
    };
    chartOptions = {
      vAxis: { title: "Temperature (C)" },
      hAxis: { title: "Date", format: "MM-yy", gridlines: { count: 7 } },
    };
    addLegend("Temperature (C)", visOptions);
  } else if (datasetSelect.getValue() === PREC) {
    dataset = prec;
    visOptions = {
      min: PREC_VIS_MIN,
      max: PREC_VIS_MAX,
      palette: ["00FFFF", "0000FF"],
    };
    chartOptions = {
      vAxis: { title: "Precipitation (mm)" },
      hAxis: { title: "Date", format: "MM-yy", gridlines: { count: 7 } },
    };
    addLegend("Precipitation (mm)", visOptions);
  } else {
    graphPanel.add(ui.Label("ERROR: Select a dataset", ERROR_MESSAGE_STYLE));
    return;
  }

  var sst = dataset.filterDate(startDate.getValue(), endDate.getValue());

  if (minStats.getValue()) {
    addLayerAndCompositeLinkAndChart(
      sst,
      ee.Reducer.min(),
      "min",
      "Minimum",
      aois,
      visOptions,
      chartOptions
    );
  }

  if (maxStats.getValue()) {
    addLayerAndCompositeLinkAndChart(
      sst,
      ee.Reducer.max(),
      "max",
      "Maximum",
      aois,
      visOptions,
      chartOptions
    );
  }

  if (meanStats.getValue()) {
    addLayerAndCompositeLinkAndChart(
      sst,
      ee.Reducer.mean(),
      "mean",
      "Average",
      aois,
      visOptions,
      chartOptions
    );
  }
}

function resetMapLayers() {
  mapLayers.reset([mapLayers.get(0)]); // Only keep points
}

function filterPointsInAOI(selectBox, aoi) {
  var fullPointsInAOI = points.filterBounds(aoi);
  var items = fullPointsInAOI
    .sort("NAME")
    .getInfo()
    .features.map(function (feature) {
      return { label: feature.properties.NAME, value: feature.geometry };
    });
  selectBox.items().reset(items);
}

// Returns our labeled legend, with a color bar and three labels representing
// the minimum, middle, and maximum values.
function addLegend(title, visOptions) {
  var min = visOptions.min;
  var max = visOptions.max;
  var labelPanel = ui.Panel(
    [
      ui.Label(min, { margin: "4px 8px" }),
      ui.Label(Math.round((max + min) / 2.0), {
        margin: "4px 8px",
        textAlign: "center",
        stretch: "horizontal",
      }),
      ui.Label(max, { margin: "4px 8px" }),
    ],
    ui.Panel.Layout.flow("horizontal")
  );
  graphPanel
    .add(ui.Label(title, LEGEND_TITLE_STYLE))
    .add(colorBar(visOptions.palette))
    .add(labelPanel);
}

// Returns a color bar widget. Makes a horizontal color bar to display the given color palette.
function colorBar(palette) {
  return ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0),
    params: {
      bbox: [0, 0, 1, 0.1],
      dimensions: "100x10",
      format: "png",
      min: 0,
      max: 1,
      palette: palette,
    },
    style: { stretch: "horizontal", margin: "0px 8px" },
  });
}

function addLayerAndCompositeLinkAndChart(
  sst,
  reducer,
  name,
  description,
  aois,
  visOptions,
  chartOptions
) {
  var aoiUnion = aois.reduce(function (left, right) {
    return left.union({ right: right, maxError: 1 });
  });
  var image = sst.reduce(reducer).clip(aoiUnion);
  var compositeLayer = ui.Map.Layer(image.visualize(visOptions)).setName(
    description
  );
  mapLayers.add(compositeLayer);

  var urlLabel = ui.Label(
    'Click here to download "' + description + '" composite'
  );
  image.getDownloadURL(
    { name: name, scale: COMPOSITE_DOWNLOAD_SCALE, format: "GEO_TIFF" },
    function (url, error) {
      if (error) {
        print("Error getting download URL for " + name + ": " + error);
      }
      urlLabel.setUrl(url);
    }
  );
  graphPanel.add(urlLabel);

  var colors = drawingLayers.getJsArray().map(function (layer) {
    return layer.getColor();
  });
  var chart = ui.Chart.image.seriesByRegion(sst, aois, reducer);
  chart.setOptions(chartOptions).setOptions({
    title: "Time Series Analysis (" + description + ")",
    colors: colors,
    legend: { position: "none" },
  });
  graphPanel.add(chart);
}

function clearWorkspaceHandler() {
  drawingLayers.forEach(function (element, _index) {
    element.geometries().reset();
  });
  resetMapLayers();
  graphPanel.clear();
}

function getPointSelectHandler(layerIndex) {
  return function (item, _widget) {
    var pointBuffer = ee
      .Geometry(item)
      .buffer({ distance: radiusInKmBox.getValue() * 1000 });
    pointBuffer.evaluate(function (geometry, _error) {
      drawingLayers.get(layerIndex).geometries().reset([geometry]);
    });
  };
}
