/** Project sharing types — v0.4 */

export interface ShareCreate {
    email: string;
    permission: 'viewer' | 'collaborator';
}

export interface ShareUpdate {
    permission: 'viewer' | 'collaborator';
}

export interface ShareResponse {
    id: string;
    project_id: string;
    user_id: string;
    username: string;
    email: string;
    permission: string;
    created_at: string;
}
