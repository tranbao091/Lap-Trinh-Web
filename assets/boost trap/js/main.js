var carouselWidth = $(".carousel-inner")[0].scrollWidth;
var carWidth = $(".carousel-item").width;
var scrollPosition = 0;
$(".carousel-control-next").on("click", function () {
  if (scrollPosition < carouselWidth - carWidth * 4) {
    console.log("next");
    scrollPosition = scrollPosition + carWidth;
    $(".carousel-inner").animate({ scrollLeft: scrollPosition }, 600);
  }
});

$(".carousel-control-prev").on("click", function () {
  if (scrollPosition > 0) {
    console.log("prev");
    scrollPosition = scrollPosition + carWidth;
    $(".carousel-inner").animate({ scrollLeft: scrollPosition }, 600);
  }
});
