FROM ubuntu:noble-20251013 AS builder
RUN apt-get update && apt-get install -y make cmake gcc-arm-none-eabi linux-tools-generic git python3 build-essential


WORKDIR /usr/local/build
RUN git clone --depth 1 https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make


COPY ./src/usbipice/worker/firmware /usr/local/firmware
WORKDIR /usr/local/firmware
RUN git clone --depth 1 --recurse-submodules -j8 https://github.com/raspberrypi/pico-sdk.git && git clone --depth 1 --recurse-submodules -j8 https://github.com/tinyvision-ai-inc/pico-ice-sdk.git

WORKDIR /usr/local/firmware/pulse_count/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make

WORKDIR /usr/local/firmware/default/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make


FROM ubuntu:noble-20251013
WORKDIR /usr/local/app

RUN apt-get update && apt-get install -y python3 python3-pip python3-venv sudo udev linux-tools-generic
RUN mkdir -p /run/udev

COPY ./ /usr/local/app/
COPY --from=builder /usr/local/build/picocom/picocom /usr/bin
COPY --from=builder /usr/local/firmware /usr/local/app/src/usbipice/worker/firmware

WORKDIR /usr/local/app
RUN python3 -m venv .venv

EXPOSE 8080