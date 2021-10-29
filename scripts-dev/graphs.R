data = read.csv('metrics.csv')
data$timestamp = as.POSIXct(strptime(data$timestamp, "%Y-%m-%d %T"))

dmr_starts = as.POSIXct(strptime("Mon Oct 11 10:47:02 2021 +0100", format="%c"))

par(mfrow=c(1,1))

# From https://davidmathlogic.com/colorblind
red =rgb(220, 50, 32, maxColorValue = 255)
blue = rgb (0, 90, 181, maxColorValue = 255)

plot(
  data$timestamp,
  100-data$imprecision,
  type="l",
  xlab="Commit time",
  ylab="Coverage (%)",
  ylim = c(60, 100),
  lty=2,
  col=red,
  main="Coverage as measured by MyPy"
)


rect(
  xleft=dmr_starts,
  xright=max(data$timestamp),
  ybottom=0,
  ytop=120,
  col=rgb(0, 0, 0, alpha=0.08),
  border=0,
)

lines(
  data$timestamp,
  data$not_anys,
  col=blue,
  lty=2,
)

legend(
  min(data$timestamp),
  95,
  legend=c("Precision", "Typed expressions"),
  col=c(red, blue),
  lty=2,
)
