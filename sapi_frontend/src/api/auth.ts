import apiClient from './client';
import type { LoginRequest, Token, User } from '@/types';

export const authApi = {
  login: async (credentials: LoginRequest): Promise<Token> => {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await apiClient.post<Token>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  loginJson: async (credentials: LoginRequest): Promise<Token> => {
    const response = await apiClient.post<Token>('/auth/login/json', credentials);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/users/me');
    return response.data;
  },
};
