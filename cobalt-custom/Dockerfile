FROM ghcr.io/imputnet/cobalt:latest

# Switch to root to create entrypoint
USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch back to node user for security
USER node

ENTRYPOINT ["/entrypoint.sh"]
