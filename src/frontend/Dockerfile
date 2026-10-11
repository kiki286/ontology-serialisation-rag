# Base image with Node
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy rest of app
COPY . .

# Build Next.js app
RUN npm run build

# Expose port
EXPOSE 3000

# Run Next.js in production
CMD ["npm", "start"]
