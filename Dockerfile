FROM python:3.12-slim

WORKDIR /app

# Copy all source files
COPY . .

# Ensure cache and output dirs exist (runtime)
RUN mkdir -p cache output storage/corpus

# Install the package (editable mode for development)
RUN pip install --no-cache-dir -e .

# Entry point
ENTRYPOINT ["noorak"]

# Default: interactive mode
CMD []

# Example usage:
# docker run -e NOORAK_API_KEY=xxx -e NOORAK_BASE_URL=... -e NOORAK_MODEL=xxx noorak "What is Tether price?"
