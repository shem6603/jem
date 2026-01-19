# J.E.M (Just Eat More) - Setup Guide

## 🎉 Project Complete!

Your e-commerce and inventory management platform is ready to use!

## Quick Start

### 1. Create a Superuser (Admin Access)

```bash
python manage.py createsuperuser
```

This will allow you to access the admin panel at `/admin/` to:
- Add Items (snacks and juices)
- Create Bundle Types
- View all orders and customers

### 2. Add Initial Data via Admin

1. Go to `http://127.0.0.1:8000/admin/`
2. Login with your superuser credentials
3. Add Items:
   - Go to **Core > Items**
   - Click "Add Item"
   - Fill in: Name, Category (Snack/Juice), Cost Price, Sell Price, Current Stock
   - Upload an image (optional)
   - Mark as "Spicy" if applicable
   - Save

4. Create Bundle Types:
   - Go to **Core > Bundle Types**
   - Click "Add Bundle Type"
   - Example: "Big Bundle" - 30 Snacks + 24 Juices
   - Example: "10/10 Bundle" - 10 Snacks + 10 Juices
   - Save

### 3. Start Using the App!

- **Dashboard**: `http://127.0.0.1:8000/dashboard/` - View profits and sales
- **Inventory**: `http://127.0.0.1:8000/inventory/` - View all items
- **New Order**: `http://127.0.0.1:8000/new-order/` - Create a bundle order

## Features Implemented

### ✅ Data Models
- **Item**: Snacks and juices with pricing, stock, images
- **BundleType**: Defines bundle rules (e.g., 30 snacks + 24 juices)
- **Customer**: Customer information
- **Order**: Links customer to bundle with auto-calculated profits
- **OrderItem**: Individual items in each order

### ✅ Bundle Builder Wizard
- **Step 1**: Select Bundle Type
- **Step 2**: Select Snacks (enforces exact count)
- **Step 3**: Select Juices (enforces exact count)
- **Step 4**: Review & Submit with customer info

### ✅ Inventory Management
- Automatic stock deduction when orders are placed
- Low stock warnings (items with < 5 units)
- Out of stock prevention
- Real-time inventory tracking

### ✅ Profit Center Dashboard
- Total All-Time Revenue
- Total All-Time Net Profit (big, bold display)
- Current Inventory Levels (low stock highlighted in red)
- Recent Sales table with Profit Margin %
- Average profit margin calculation

### ✅ UI/UX Features
- **Mobile-First Design**: Large, tappable buttons for phone use
- **Vibrant Theme**: Orange, Red, Yellow colors reflecting snacks
- **Tailwind CSS**: Modern, responsive design
- **Progress Indicators**: Visual feedback in bundle builder
- **Real-time Validation**: Prevents invalid selections

## Admin Panel Features

The admin interface includes:
- **Item Management**: Edit stock, prices, upload images
- **Bundle Type Management**: Create and manage bundle rules
- **Order Management**: View all orders with financial details
- **Customer Management**: View customer information and order history

## Database

- **Development**: SQLite (default)
- **Production (GoDaddy)**: MySQL (`jem_customer` database)

## Next Steps

1. **Add Sample Data**:
   - Add at least 10-15 snacks
   - Add at least 10-15 juices
   - Create 2-3 bundle types

2. **Test the Bundle Builder**:
   - Create a test order
   - Verify stock is deducted
   - Check profit calculations

3. **Customize** (Optional):
   - Add more fields to models if needed
   - Customize colors in `base.html`
   - Add email notifications
   - Add order status workflow

## Important Notes

- **Stock Management**: Stock is automatically deducted when orders are created
- **Profit Calculation**: All financial calculations are automatic
- **Image Uploads**: Images are stored in `media/items/` directory
- **Session Management**: Bundle builder uses Django sessions to track selections

## Troubleshooting

**Issue**: "No items available" in bundle builder
- **Solution**: Add items via admin panel first

**Issue**: Can't select enough items
- **Solution**: Ensure you have enough stock. Check inventory page for stock levels

**Issue**: Images not displaying
- **Solution**: Run `python manage.py collectstatic` and ensure MEDIA_URL is configured

## Production Deployment

See `DEPLOYMENT.md` for GoDaddy deployment instructions. The app is already configured for:
- Python 3.11.13
- MySQL database (`jem_customer`)
- Domain: `jem.rixsoft.org`

## Support

For issues or questions:
1. Check Django admin panel for data
2. Review error messages in console
3. Check database connections
4. Verify environment variables are set

---

**Ready to start selling! 🚀**
