import { Request, Response } from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { randomUUID } from 'crypto';
import { postgresService } from '../services/postgres.service';

class AuthController {
  async signUp(req: Request, res: Response) {
    try {
      const { email, password } = req.body;

      if (!email || !password) {
        return res.status(400).json({ error: 'Email and password required' });
      }

      // Check if user exists
      const existingUser = await postgresService.getUserByEmail(email);
      if (existingUser) {
        return res.status(409).json({ error: 'User already exists' });
      }

      // Hash password
      const hashedPassword = await bcrypt.hash(password, 10);

      // Create user
      const userId = randomUUID();
      await postgresService.createUser({
        id: userId,
        email,
        passwordHash: hashedPassword,
      });

      // Generate JWT
      const secret = process.env.JWT_SECRET || 'default-secret';
      const token = jwt.sign(
        { userId, email },
        secret,
        { expiresIn: '7d' }
      );

      res.status(201).json({
        token,
        userId,
        email,
      });
    } catch (error) {
      console.error('SignUp Error:', error);
      res.status(500).json({ error: 'Failed to create user' });
    }
  }

  async signIn(req: Request, res: Response) {
    try {
      const { email, password } = req.body;

      if (!email || !password) {
        return res.status(400).json({ error: 'Email and password required' });
      }

      // Get user
      const user = await postgresService.getUserByEmail(email);
      if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      // Verify password
      const validPassword = await bcrypt.compare(password, user.password_hash);
      if (!validPassword) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      // Generate JWT
      const secret = process.env.JWT_SECRET || 'default-secret';
      const token = jwt.sign(
        { userId: user.id, email: user.email },
        secret,
        { expiresIn: '7d' }
      );

      res.json({
        token,
        userId: user.id,
        email: user.email,
      });
    } catch (error) {
      console.error('SignIn Error:', error);
      res.status(500).json({ error: 'Failed to sign in' });
    }
  }

  async signOut(req: Request, res: Response) {
    // In a stateless JWT system, signout is handled client-side
    // If you want to implement token blacklisting, add it here
    res.json({ success: true });
  }

  async refreshToken(req: Request, res: Response) {
    // Implement token refresh logic if needed
    res.status(501).json({ error: 'Not implemented' });
  }
}

export const authController = new AuthController();
