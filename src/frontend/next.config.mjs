/** @type {import('next').NextConfig} */
const nextConfig = {
  logging: {
    fetches: {
      fullUrl: true,
    },
    headers: true,
    cookies: true,
  },
};

export default nextConfig;
