# StockWise Application

## SSL and Nginx Setup

This application uses Nginx as a reverse proxy to handle SSL/TLS termination. For security reasons, SSL certificates are not included in the repository.

### Initial Setup

1. Create required directories:
```bash
mkdir -p nginx/ssl nginx/logs
```

2. Generate SSL certificates:

For development (self-signed certificates):
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt
```

For production:
- Obtain SSL certificates from a certified provider (e.g., Let's Encrypt)
- Place the certificates in the `nginx/ssl` directory:
  - Certificate file: `nginx/ssl/certificate.crt`
  - Private key file: `nginx/ssl/private.key`

### Certificate Requirements

The following files must be placed in the `nginx/ssl` directory:
- `certificate.crt`: Your SSL certificate
- `private.key`: Your private key

### Local Development

1. For local development, you can use self-signed certificates:
```bash
# Generate self-signed certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt

# When prompted, use these settings:
# Common Name (CN): localhost
# The rest can be left empty
```

2. Add the self-signed certificate to your system's trusted certificates (optional):
- MacOS: Double click the certificate in Finder and add it to your System keychain
- Linux: Follow your distribution's instructions for adding trusted certificates
- Windows: Double click the certificate and install it in the Trusted Root Certification Authorities

### Production Deployment

For production environments:
1. Obtain SSL certificates from a trusted provider
2. Place the certificates in the `nginx/ssl` directory
3. Ensure proper permissions:
```bash
chmod 600 nginx/ssl/private.key
chmod 644 nginx/ssl/certificate.crt
```

### Security Notes

- Never commit SSL certificates or private keys to the repository
- Keep backup copies of your certificates and keys in a secure location
- Set up automatic certificate renewal if using Let's Encrypt
- Regularly check certificate expiration dates

### Troubleshooting

Common issues:

1. SSL certificate not found:
```bash
# Check if certificates exist
ls -la nginx/ssl/

# Check permissions
chmod 600 nginx/ssl/private.key
chmod 644 nginx/ssl/certificate.crt
```

2. Nginx container won't start:
```bash
# Check Nginx logs
docker compose logs nginx

# Verify certificate paths in nginx/conf.d/default.conf
```

3. Certificate errors in browser:
- For development: Add self-signed certificate to system trust store
- For production: Verify certificate chain is complete