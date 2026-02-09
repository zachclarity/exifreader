\
# Java 21 Lambda container image with real Tesseract OCR (built from source)
# Optimizations:
# - build in multi-stage
# - use tessdata_fast for speed
# - Java flags set via JAVA_TOOL_OPTIONS (set in compose + can be overridden)

ARG TESSERACT_VERSION=5.3.4
ARG LEPTONICA_VERSION=1.84.1

############################
# 1) Build Java shaded JAR
############################
FROM maven:3.9-eclipse-temurin-21 AS java-build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package

###############################################
# 2) Build leptonica + tesseract from source
###############################################
FROM amazonlinux:2023 AS tess-build
ARG TESSERACT_VERSION
ARG LEPTONICA_VERSION

RUN dnf -y update && \
    dnf -y install \
      gcc gcc-c++ make cmake autoconf automake libtool pkgconfig \
      zlib-devel libjpeg-turbo-devel libpng-devel libtiff-devel \
      git wget curl xz tar gzip && \
    dnf clean all

WORKDIR /build

# Leptonica
RUN curl -L -o leptonica.tar.gz https://github.com/DanBloomberg/leptonica/releases/download/${LEPTONICA_VERSION}/leptonica-${LEPTONICA_VERSION}.tar.gz && \
    tar -xzf leptonica.tar.gz && \
    cd leptonica-${LEPTONICA_VERSION} && \
    ./configure --prefix=/opt/tesseract && \
    make -j"$(nproc)" && \
    make install

# Tesseract
RUN curl -L -o tesseract.tar.gz https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSION}.tar.gz && \
    tar -xzf tesseract.tar.gz && \
    cd tesseract-${TESSERACT_VERSION} && \
    ./autogen.sh && \
    PKG_CONFIG_PATH=/opt/tesseract/lib/pkgconfig ./configure --prefix=/opt/tesseract && \
    make -j"$(nproc)" && \
    make install

# tessdata_fast (English)
RUN mkdir -p /opt/tessdata && \
    curl -L -o /opt/tessdata/eng.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata

###############################################
# 3) Final Lambda image
###############################################
FROM public.ecr.aws/lambda/java:21

# Copy tesseract + data
COPY --from=tess-build /opt/tesseract /opt/tesseract
COPY --from=tess-build /opt/tessdata /opt/tessdata

# Copy function jar
COPY --from=java-build /app/target/ocr-lambda-image.jar ${LAMBDA_TASK_ROOT}/lib/ocr-lambda-image.jar

# OCR env
ENV PATH="/opt/tesseract/bin:${PATH}"
ENV LD_LIBRARY_PATH="/opt/tesseract/lib:${LD_LIBRARY_PATH}"
ENV TESSDATA_PREFIX="/opt/tessdata"
ENV REAL_OCR="true"
ENV TESSERACT_BIN="/opt/tesseract/bin/tesseract"
ENV TESS_LANG="eng"

# LocalStack S3 endpoint inside docker network
ENV LOCALSTACK_ENDPOINT="http://localstack:4566"
ENV OCR_BUCKET="ocr-images"

CMD ["com.zactonics.ocr.OcrHandler::handleRequest"]
